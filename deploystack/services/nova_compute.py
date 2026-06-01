# Configure an Compute Node

import os
import json

from ..utils.core.commands import run_command, run_commands, os_run_output
from ..utils.core.system_utils import has_hw_virtualization, service_exists
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option
from ..utils.core import colors

nova_conf= "/etc/nova/nova.conf"
nova_compute_conf= "/etc/nova/nova-compute.conf"

def get_flavors(env=None):
    raw = os_run_output(
        ["openstack", "flavor", "list", "-f", "json"],
        env=env
    )

    return json.loads(raw or "[]")

def install_pkgs():

    if not apt_install(["nova-compute"], ux_text=f"Installing Nova Compute package...") : return False

    return True

def conf_nova_compute(config):

    cpu_allocation_ratio = get(config, "compute.CPU_ALLOCATION_RATIO")
    ram_allocation_ratio = get(config, "compute.RAM_ALLOCATION_RATIO")
    disk_allocation_ratio = get(config, "compute.DISK_ALLOCATION_RATIO")
      
    virt_type = get(config, "compute.NOVA_COMPUTE_VIRT_TYPE")

    set_conf_option(nova_conf, "DEFAULT", "cpu_allocation_ratio", str(cpu_allocation_ratio))
    set_conf_option(nova_conf, "DEFAULT", "ram_allocation_ratio", str(ram_allocation_ratio))
    set_conf_option(nova_conf, "DEFAULT", "disk_allocation_ratio", str(disk_allocation_ratio))

    if not has_hw_virtualization():
        set_conf_option(nova_compute_conf, "libvirt", "virt_type", "qemu")
    else:
        set_conf_option(nova_compute_conf, "libvirt", "virt_type", virt_type)

    set_conf_option(nova_conf, "scheduler", "discover_hosts_in_cells_interval", "300")

def finalize():

    print()

    services_to_restart = [
        "nova-scheduler", 
        "nova-compute", 
        "apache2"
    ]

    if service_exists("nova-api.service"):
        services_to_restart.insert(0, "nova-api")

    if not run_command(["systemctl", "restart"] + services_to_restart, "Restarting Nova Compute services..."): return False
    
    print()

    cell_discover_hosts_migration_cmd = [
    "sudo", "-u", "nova",
    "nova-manage", "cell_v2", "discover_hosts", "--verbose"
]
    
    if not run_command(cell_discover_hosts_migration_cmd, "Discovering the Compute Node on Cell0...") : return False

    return True

def create_default_flavors(env):

    flavors_list = get_flavors(env)

    existing_flavors = {
        (a["Name"], str(a["RAM"]), str(a["VCPUs"]))
        for a in flavors_list
    }

    default_flavors = [
        {"name": "m1.tiny", "id": 1, "ram": 512, "disk": 1, "vcpus": 1},
        {"name": "m1.small", "id": 2, "ram": 2048, "disk": 20, "vcpus": 1},
        {"name": "m1.medium", "id": 3, "ram": 4096, "disk": 40, "vcpus": 2},
        {"name": "m1.large", "id": 4, "ram": 8192, "disk": 80, "vcpus": 4},
        {"name": "m1.xlarge", "id": 5, "ram": 16384, "disk": 160, "vcpus": 8},
    ]

    flavors_create_cmds = []

    for f in default_flavors:
        if (f["name"], str(f["ram"]), str(f["vcpus"])) not in existing_flavors:
            flavors_create_cmds.append([
                "openstack", "flavor", "create",
                "--id", str(f["id"]),
                "--ram", str(f["ram"]),
                "--disk", str(f["disk"]),
                "--vcpus", str(f["vcpus"]),
                str(f["name"])
            ])

    if flavors_create_cmds:
        print()
        if not run_commands(flavors_create_cmds, "Creating default flavors...", env=env):
            return False

    return True
    
def run_setup_nova_compute(config, env):
     
    if not install_pkgs(): return False   
    conf_nova_compute(config)   
    if not finalize(): return False   
    if not create_default_flavors(env): return False
    
    print(f"\n{colors.GREEN}Compute Node configured successfully!{colors.RESET}\n")
    return True