
import os
import subprocess

from pathlib import Path

from ....utils.core.system_utils import is_module_loaded, kernel_module_exists
from ....utils.core.commands import run_command
from ....utils.core.system_utils import service_exists, is_debian

encap_modules = {
    "vxlan": ["vport_vxlan", "vxlan"],
    "geneve": ["vport_geneve", "geneve"],
}

ifaces_config_exclude_patterns = {
    "openvswitch",
    "br-shares",
}

def restart_ovs_services():
    if service_exists("nova-api.service"):
        if not run_command(["systemctl", "restart", "nova-api"], "Restarting Nova API...", False, None, 3, 5): return False
    
    if service_exists("neutron-server.service"):
        if not run_command(["systemctl", "restart", "neutron-server", "neutron-openvswitch-agent", "neutron-dhcp-agent", "neutron-metadata-agent", "neutron-l3-agent", "nova-compute"], "Restarting Neutron OVS services...", False, None, 3, 5): return False
    elif service_exists("neutron-api.service") and is_debian():
        if not run_command(["systemctl", "restart", "neutron-api", "neutron-rpc-server", "neutron-l3-agent", "neutron-openvswitch-agent", "neutron-metadata-agent", "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False  
    else:
        if not run_command(["systemctl", "restart", "neutron-periodic-workers", "neutron-rpc-server", "apache2", "neutron-openvswitch-agent", "neutron-dhcp-agent", "neutron-metadata-agent", "neutron-l3-agent", "nova-compute"], "Restarting Neutron OVS services...", False, None, 3, 5): return False

def restart_ovn_services():
    
    if service_exists("nova-api.service"):
        if not run_command(["systemctl", "restart", "nova-api"], "Restarting Nova API...", False, None, 3, 5): return False

    if service_exists("neutron-server.service"):
        if not run_command(
            ["systemctl", "restart",
            "neutron-server",
            "neutron-ovn-metadata-agent",
            "nova-compute"],
            "Restarting Neutron and Nova services...", False, None, 3, 5
        ):
            return False
    elif service_exists("neutron-api.service") and is_debian():
        if not run_command(["systemctl", "restart", "neutron-api", "neutron-rpc-server", "neutron-ovn-metadata-agent", "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False
    else:
        if not run_command(
            ["systemctl", "restart",
            "neutron-periodic-workers", "apache2",
            "neutron-ovn-metadata-agent",
            "nova-compute"],
            "Restarting Neutron and Nova services...", False, None, 3, 5
        ):
            return False
        
    return True

def enable_kernel_module(module_names: list[str]) -> bool:
    try:
        for module_name in module_names:
            if not is_module_loaded(module_name) and kernel_module_exists(module_name):
                if not run_command(["modprobe", module_name], f"Enabling '{module_name}' kernel module... ") : return False

        return True
    except subprocess.CalledProcessError:
        return False
    except:
        return False

def write_permanent_modules_conf(file_path: str, modules: list[str]):
    modules_file = Path(file_path)
    
    modules_file.parent.mkdir(parents=True, exist_ok=True)
    modules_file.write_text("\n".join(modules) + "\n")

def enable_ipv4_forwarding() -> bool:
    with open("/proc/sys/net/ipv4/ip_forward") as f:
        ip_forward = int(f.read().strip())

    if ip_forward != 1:

        if not run_command(
            ["sysctl", "-w", "net.ipv4.ip_forward=1"],
            "Enabling IPv4 IP Forwarding..."
        ):
            return False
        else:
            print()

    sysctl_file = "/etc/sysctl.d/99-openstack-forwarding.conf"

    if not os.path.exists(sysctl_file):
        with open(sysctl_file, "w") as f:
            f.write("net.ipv4.ip_forward = 1\n")

    return True
