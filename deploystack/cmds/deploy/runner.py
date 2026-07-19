import os
import sys

from ...utils.apt.apt import apt_update, apt_install
from ...utils.config.parser import parse_config, get, to_bool
from ...utils.config.parser import parse_config, get, resolve_vars
from ...utils.core import colors
from ...utils.core.system_utils import has_hw_virtualization, check_ifupdown
from ...utils.network.net_utils import get_active_interface
from ...utils.tasks.check_deployment import mark_deployment_complete, MARKER_FILE
from ...utils.core.system_utils import is_debian
from ...utils.core.commands import build_openstack_env

from ...utils.lvm.loopback import set_lvm_filter

from ...utils.config.validator import validate_all

from ...services.prereqs import run_setup_prereqs
from ...services.mariadb import run_setup_mariadb
from ...services.keystone import run_setup_keystone
from ...services.glance import run_setup_glance
from ...services.cinder import run_setup_cinder
from ...services.placement import run_setup_placement
from ...services.nova import run_setup_nova
from ...services.nova_compute import run_setup_nova_compute
from ...services.neutron import run_setup_neutron
from ...services.manila import run_setup_manila
from ...services.horizon import run_setup_horizon

from ...utils.config.helpers import parse_bool

def deploy(config_file):

    config = parse_config(config_file)
    config = resolve_vars(config)
  
    public_iface = get_active_interface()

    env = build_openstack_env(config)

    create_ovs_bridges = get(config, "ovs.CREATE_BRIDGES")
    create_ovn_bridges = get(config, "ovn.CREATE_BRIDGES")

    devices = []

    if (create_ovn_bridges or create_ovs_bridges) and os.path.exists(f"/sys/class/net/{public_iface}/wireless"):
        print(f"{colors.RED}Wi-Fi interfaces are not supported for OVS bridge networking, Switch to Ethernet to continue OpenStack deployment.{colors.RESET}")

        sys.exit(1)
        return False
  
    if not check_ifupdown():
        print(f"OpenStack deployment cannot proceed because {colors.GREEN}ifupdown{colors.RESET} is not installed on this system.\nPlease install the {colors.GREEN}ifupdown{colors.RESET} package and ensure your network is properly configured before retrying the deployment.")
        
        sys.exit(1)
        return False
        
    if not has_hw_virtualization():
        print(f"{colors.YELLOW}Warning: No hardware virtualization detected – QEMU hypervisor will be used and Nova instances will be emulated with lower performance{colors.RESET}\n")

    if not validate_all(config):
        print("\nPlease review and correct any errors reported in the configuration above before retrying the OpenStack deployment again.")

        sys.exit(1)
        return False 
    
    install_manila = parse_bool(get(config, "optional_services.INSTALL_MANILA", False))

    install_cinder = parse_bool(get(config, "optional_services.INSTALL_CINDER", False))
    install_horizon = parse_bool(get(config, "optional_services.INSTALL_HORIZON", False))

    is_lvm_manila_backend_enabled = get(config, "manila.BACKEND") == "lvm"

    if install_cinder:
        cinder_pv = get(config, "cinder.lvm.PHYSICAL_VOLUME")
        cinder_loop_dev = get(config, "cinder.lvm.CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_PATH")

        devices.append(cinder_pv or cinder_loop_dev)

    if install_manila and is_lvm_manila_backend_enabled:
        manila_pv = get(config, "manila.lvm.PHYSICAL_VOLUME")
        manila_loop_dev = get(config, "manila.lvm.LVM_LOOP_PATH")

        devices.append(manila_pv or manila_loop_dev)

    if devices:
        if not set_lvm_filter(devices):
            return False

    ip_address = get(config, "network.HOST_IP")

    print("OpenStack Deployment Started\n")
    
    print("Setting up prerequirements\n")
    if not run_setup_prereqs(config): 
        sys.exit(1)
        return False

    print("Setting up MariaDB\n")
    if not run_setup_mariadb(config): 
        sys.exit(1)
        return False

    print("Setting up Keystone\n")
    if not run_setup_keystone(config, env):
        sys.exit(1)
        return False

    print("Setting up Glance\n")
    if not run_setup_glance(config, env):
        sys.exit(1)
        return False
    
    if install_cinder:
        print("Setting up Cinder\n")
        if not run_setup_cinder(config):
            sys.exit(1)
            return False
        
    print("Setting up Placement\n")
    if not run_setup_placement(config):
        sys.exit(1)
        return False
    
    print("Setting up Nova\n")
    if not run_setup_nova(config, env):
        sys.exit(1)
        return False
    
    print("Setting up a Compute Node\n")
    if not run_setup_nova_compute(config, env): 
        sys.exit(1)
        return False

    print("Setting up Neutron\n")
    if not run_setup_neutron(config, env): 
        sys.exit(1)
        return False
    
    if install_manila:
        print("Setting up Manila\n")
        if not run_setup_manila(config, env):
            sys.exit(1)
            return False
    
    if install_horizon:
        print("Setting up Horizon\n")
        if not run_setup_horizon(config): 
            sys.exit(1) 
            return False
    
    print(f"\n*** {colors.GREEN}OpenStack Deployment Completed Successfully!{colors.RESET} ***")

    print(f"\n{colors.BRIGHT_BLUE}Access your OpenStack services:{colors.RESET}")

    if install_horizon:
        if is_debian():
            print(f" - Horizon Dashboard: http://{ip_address}/horizon")
        else:
            print(f" - Horizon Dashboard: http://{ip_address}/dashboard")

    print(f" - Keystone API:      http://{ip_address}:5000/\n")

    print(f"{colors.YELLOW}Tip:{colors.RESET} Use the ADMIN credentials you configured in your config file to log in.")
    print(f"{colors.YELLOW}Note:{colors.RESET} Make sure your firewall allows HTTP/HTTPS access to this host.")
    print(f"{colors.YELLOW}Credentials Scripts:{colors.RESET} You can find them in /root/admin-openrc.sh and /root/demo-openrc.sh\n")

    mark_deployment_complete()

    return True