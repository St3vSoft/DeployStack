import os
import re
import glob

from pprint import pformat

from ....utils.apt.apt import apt_install
from ....utils.config.parser import get
from ....utils.core import colors

from ....utils.core.system_utils import is_debian


local_settings_file = "/etc/openstack-dashboard/local_settings.py"
manila_shares_settings_file = "/etc/openstack-dashboard/local_settings.d/_90_manila_shares.py"

manila_ui_enabled_dir = "/usr/lib/python3/dist-packages/manila_ui/local/enabled/"
openstack_dashboard_local_enabled_dir = "/usr/share/openstack-dashboard/openstack_dashboard/local/enabled/"

def install_pkgs():

    if not apt_install(["python3-manila-ui"], "Installing Python3 Manila UI Package..."):
        return False
    
    return True

def disable_unsupported_protocols_options(config):

    protocols = get(config, "manila.SHARE_PROTOCOLS") or []

    current_settings_file = ""

    if is_debian():
        current_settings_file = manila_shares_settings_file
    else:
        current_settings_file = local_settings_file

    try:
        OPENSTACK_MANILA_FEATURES = {
            "enabled_share_protocols": protocols
        }

        with open(current_settings_file, "r") as f:
            content = f.read()

        content = re.sub(
            r"OPENSTACK_MANILA_FEATURES\s*=\s*\{.*?\}\s*",
            "",
            content,
            flags=re.DOTALL
        )

        content += (
            "\nOPENSTACK_MANILA_FEATURES = "
            + pformat(OPENSTACK_MANILA_FEATURES)
            + "\n"
        )

        with open(current_settings_file, "w") as f:
            f.write(content)

        return True

    except Exception as e:
        print(f"\n{colors.ERROR}Unable to update Horizon Manila settings: {e}{colors.RESET}\n")
        return False

def disable_dhss_dashboard_panels():

    enabled_dirs = [
        "/usr/lib/python3/dist-packages/openstack_dashboard/enabled",
        "/usr/lib/python3/dist-packages/manila_ui/local/enabled",
    ]

    dhss_panels = [
        "_9040_manila_admin_add_share_networks_panel_to_share_panel_group.py",
        "_9040_manila_project_add_share_networks_panel_to_share_panel_group.py",
        "_9050_manila_admin_add_security_services_panel_to_share_panel_group.py",
        "_9050_manila_project_add_security_services_panel_to_share_panel_group.py",
        "_9060_manila_admin_add_share_servers_panel_to_share_panel_group.py",
        "_9070_manila_admin_add_share_instances_panel_to_share_panel_group.py",
        "_9080_manila_admin_add_share_groups_panel_to_share_panel_group.py",
        "_9080_manila_project_add_share_groups_panel_to_share_panel_group.py",
        "_9085_manila_admin_add_share_group_snapshots_panel_to_share_panel_group.py",
        "_9085_manila_project_add_share_group_snapshots_panel_to_share_panel_group.py",
        "_9090_manila_admin_add_share_group_types_panel_to_share_panel_group.py",
    ]

    for enabled_dir in enabled_dirs:
        for panel in dhss_panels:
            src = os.path.join(enabled_dir, panel)
            dst = src + ".disabled"

            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    os.rename(src, dst)
                except OSError as e:
                    print(f"{colors.RED}Error: Unable to disable '{panel}' panel with exception: {e}{colors.RESET}")
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

def setup_manila_horizon(config):

    print()

    backend = get(config, "manila.BACKEND")
    is_generic = backend == "generic"

    if not os.path.exists("/usr/share/openstack-dashboard"):
        print(f"{colors.RED}Error: Horizon is not yet installed{colors.RESET}")
        return False

    if not install_pkgs():
        return False

    if not is_generic:
        if not disable_dhss_dashboard_panels():
            return False

    if not add_dashboard_ui_symlink():
        return False

    if not disable_unsupported_protocols_options(config):
        return False

    return True