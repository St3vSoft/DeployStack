import os
import sys

from ...utils.config.parser import parse_config, get, resolve_vars
from ...utils.core import colors
from ...utils.core.system_utils import has_hw_virtualization, check_ifupdown
from ...utils.network.net_utils import get_active_interface
from ...utils.tasks.check_deployment import mark_deployment_complete
from ...utils.core.system_utils import is_debian
from ...utils.core.commands import build_openstack_env

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

from ...services.utils import get_base_host

from ...utils.config.helpers import parse_bool

def _deployment_failed(step=None):
    message = "OpenStack Deployment Failed"

    if step:
        message += f" during: {step}"

    print(f"\n{colors.RED}*** {message}! ***{colors.RESET}\n\n")

    print(
        f"The deployment could not be completed due to an unexpected error.\n"
        f"Possible causes include:\n"
        f"  - Incorrect configuration or missing dependencies.\n"
        f"  - Network, database or authentication issues.\n"
        f"  - OpenStack service installation or configuration failures.\n"
        f"  - Insufficient system resources or permissions.\n"
    )

    print(
        f"{colors.BRIGHT_BLUE}Recommended actions:{colors.RESET}\n"
        f"  - Review the error messages displayed above.\n"
        f"  - Check the affected service logs and configuration.\n"
        f"  - Resolve the issue before retrying the deployment.\n"
    )

    return False

def deploy(config_file, config_generated: bool = False):

    config = parse_config(config_file)
    config = resolve_vars(config)
  
    public_iface = get_active_interface()

    env = build_openstack_env(config)

    create_ovs_bridges = get(config, "ovs.CREATE_BRIDGES")
    create_ovn_bridges = get(config, "ovn.CREATE_BRIDGES")

    if (create_ovn_bridges or create_ovs_bridges) and os.path.exists(f"/sys/class/net/{public_iface}/wireless"):
        print(f"{colors.RED}Wi-Fi interfaces are not supported for OVS bridge networking, Switch to Ethernet to continue OpenStack deployment.{colors.RESET}")

        sys.exit(1)
        return False
  
    if not check_ifupdown():
        print(
            f"OpenStack deployment cannot proceed because "
            f"{colors.GREEN}ifupdown{colors.RESET} is not installed on this system.\n"
            f"Please install the {colors.GREEN}ifupdown{colors.RESET} package and ensure "
            f"your network is properly configured before retrying the deployment.\n\n"
            f"Documentation: https://github.com/St3vSoft/DeployStack/wiki/OpenStack-Deployment-Guide\n"
        )

        sys.exit(1)
        return False
        
    if not has_hw_virtualization():
        print(f"{colors.YELLOW}Warning: No hardware virtualization detected – QEMU hypervisor will be used and Nova instances will be emulated with lower performance{colors.RESET}\n")

    if not validate_all(config):
        print("\nPlease review and correct any errors reported in the configuration above before retrying the OpenStack deployment again.")

        if config_generated:
            os.remove(config_file)

        sys.exit(1)
        return False 
    
    install_manila = parse_bool(get(config, "optional_services.INSTALL_MANILA", False))
    install_cinder = parse_bool(get(config, "optional_services.INSTALL_CINDER", False))
    install_horizon = parse_bool(get(config, "optional_services.INSTALL_HORIZON", False))

    os.makedirs("/var/lib/deploystack/", exist_ok=True)

    print("OpenStack Deployment Started\n")

    setup_steps = [
        ("Setting up prerequirements", run_setup_prereqs, (config,)),
        ("Setting up MariaDB", run_setup_mariadb, (config,)),
        ("Setting up Keystone", run_setup_keystone, (config, env)),
        ("Setting up Glance", run_setup_glance, (config, env)),
    ]

    if install_cinder:
        setup_steps.append(("Setting up Cinder", run_setup_cinder, (config, env)))

    setup_steps.extend([
        ("Setting up Placement", run_setup_placement, (config,)),
        ("Setting up Nova", run_setup_nova, (config, env)),
        ("Setting up a Compute Node", run_setup_nova_compute, (config, env)),
        ("Setting up Neutron", run_setup_neutron, (config, env)),
    ])

    if install_manila:
        setup_steps.append(("Setting up Manila", run_setup_manila, (config, env)))

    if install_horizon:
        setup_steps.append(("Setting up Horizon", run_setup_horizon, (config,)))

    for description, setup_func, args in setup_steps:
        print(f"{description}\n")

        if not setup_func(*args):
            _deployment_failed(description)
            sys.exit(1)
    
    print(f"\n*** {colors.GREEN}OpenStack Deployment Completed Successfully!{colors.RESET} ******")

    print(f"\n{colors.BRIGHT_BLUE}Access your OpenStack services:{colors.RESET}")

    if install_horizon:
        if is_debian():
            print(f" - Horizon Dashboard: http://{get_base_host(config)}/horizon")
        else:
            print(f" - Horizon Dashboard: http://{get_base_host(config)}/dashboard")

    print(f" - Keystone API:      http://{get_base_host(config)}:5000/\n")

    print(f"{colors.YELLOW}Tip:{colors.RESET} Use the ADMIN credentials you configured in your config file to log in.")
    print(f"{colors.YELLOW}Note:{colors.RESET} Make sure your firewall allows HTTP/HTTPS access to this host.")
    print(f"{colors.YELLOW}Credentials Scripts:{colors.RESET} You can find them in /root/admin-openrc.sh and /root/demo-openrc.sh\n")

    mark_deployment_complete()

    return True