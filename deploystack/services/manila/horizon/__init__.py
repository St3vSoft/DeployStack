import os
import glob

from ....utils.apt.apt import apt_install
from ....utils.core import colors

manila_ui_enabled_dir = "/usr/lib/python3/dist-packages/manila_ui/local/enabled/"
openstack_dashboard_local_enabled_dir = "/usr/share/openstack-dashboard/openstack_dashboard/local/enabled/"

def install_pkgs():

    if not apt_install(["python3-manila-ui"], "Installing Python3 Manila UI Packages..."):
        return False
    
    return True

def add_dashboard_ui_symlink():

    try:
        if not os.path.isdir(manila_ui_enabled_dir):
            print(
                f"{colors.RED}Error: Manila UI enabled directory not found: {manila_ui_enabled_dir}{colors.RESET}"
            )
            return False
        
        os.makedirs(openstack_dashboard_local_enabled_dir, exist_ok=True)

        files = glob.glob(os.path.join(manila_ui_enabled_dir, "*"))

        if not files:
            print(
                f"{colors.RED}Error: no Manila Horizon dashboard files found{colors.RESET}"
            )
            return False
        
        for file in files:
            link_name = os.path.join(openstack_dashboard_local_enabled_dir, os.path.basename(file))

            if os.path.islink(link_name) or os.path.exists(link_name):
                continue

            os.symlink(file, link_name)

    except Exception as e:
        print(f"{colors.RED}Error: failed to create Manila Horizon symlinks: {e}{colors.RESET}")
        return False
    
    return True

def setup_manila_horizon():

    if not os.path.exists("/usr/share/openstack-dashboard"):
        print(
            f"{colors.RED}Error: Horizon is not yet installed{colors.RESET}"
        )
        return False

    if not install_pkgs() : return False
    if not add_dashboard_ui_symlink() : return False

    return True