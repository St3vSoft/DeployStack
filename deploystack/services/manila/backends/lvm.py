# Configure the LVM Backend (Share Node)

import os
import json
import pwd
import grp
import subprocess
import shutil
import time

from ....utils.core.commands import run_command, os_run_output, os_run
from ....utils.apt.apt import apt_install
from ....utils.config.parser import get
from ....utils.config.setter import set_conf_option

from ....utils.lvm.loopback import write_loopback_lvm_env, setup_loopback_service
from ....utils.lvm import get_vg_for_pv, ensure_system_user_with_run_command

from ....templates import MANILA_LVM_NETWORK_SERVICE, MANILA_BRIDGE_IP_SCRIPT

from .helpers import wait_manila_backend, wait_share_available
from ....utils.config.helpers import parse_bool

from ....utils.core import colors

manila_conf = "/etc/manila/manila.conf"

def install_pkgs():

    print()

    if not apt_install(["manila-share", "lvm2", "nfs-kernel-server"], "Installing Manila Share LVM Packages..."):
        return False
    
    return True

def conf_lvm(config):

    lvm_physical_volume = get(config, "manila.backends.lvm.PHYSICAL_VOLUME")
    lvm_image_file_path = get(config, "manila.backends.lvm.MANILA_LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "manila.backends.lvm.MANILA_LVM_LOOP_PATH")
    lvm_image_size_in_gb = get(config, "manila.backends.lvm.MANILA_LVM_IMAGE_SIZE_IN_GB")

    vg_name = get(config, "manila.backends.lvm.SHARE_VOLUME_GROUP")

    if lvm_physical_volume:
        lvm_dev = lvm_physical_volume
    else:
        lvm_dev = lvm_loop_dev

        if not os.path.exists(lvm_image_file_path):

            print() 

            truncate_cmd = [
                "truncate",
                "-s",
                f"{lvm_image_size_in_gb}G",
                lvm_image_file_path
            ]

            if not run_command(truncate_cmd, "Allocating LVM disk image..."):
                return False

            if not ensure_system_user_with_run_command("manila"):
                return False

            uid = pwd.getpwnam("manila").pw_uid
            gid = grp.getgrnam("manila").gr_gid

            os.chown(lvm_image_file_path, uid, gid)
            os.chmod(lvm_image_file_path, 0o600)

            print()

        try:
            losetup_output = subprocess.check_output(
                ["losetup", "-j", lvm_image_file_path],
                text=True
            )
        except subprocess.CalledProcessError:
            losetup_output = ""

        if lvm_image_file_path not in losetup_output:
            if not run_command(
                ["losetup", lvm_loop_dev, lvm_image_file_path],
                f"Associating {lvm_image_file_path} to {lvm_loop_dev}..."
            ):
                return False
            
    vg = get_vg_for_pv(lvm_dev)

    if vg is None:

        print() 

        if not run_command(
            ["pvcreate", lvm_dev],
            f"Creating physical volume on {lvm_dev}..."
        ):
            return False

        if not run_command(
            ["vgcreate", vg_name, lvm_dev],
            f"Creating volume group {vg_name}..."
        ):
            return False

    elif vg == vg_name:
        pass

    else:
        print(
            f"{colors.RED}"
            f"{lvm_dev} already belongs to VG '{vg}', expected '{vg_name}'"
            f"{colors.RESET}"
        )
        return False

    return True

def conf_lvm_manila(config):

    SERVICE_PATH = "/etc/systemd/system/manila-lvm-network.service"
    script_path = "/usr/local/bin/manila-br-ex-ip.sh"

    backend_name = get(config, "manila.backends.lvm.BACKEND_NAME").lower()

    protocols = get(config, "manila.SHARE_PROTOCOLS", default=["NFS"])
    enabled_share_protocols = ",".join(protocols)

    driver_handles_share_servers = parse_bool(get(config, "manila.backends.lvm.DRIVER_HANDLES_SHARE_SERVERS"), False)

    vg_name = get(config, "manila.backends.lvm.SHARE_VOLUME_GROUP")
    
    public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")
    public_cidr = get(config, "neutron.public_network.PUBLIC_SUBNET_CIDR")

    share_export_ip = get(config, "manila.backends.lvm.SHARE_EXPORT_IP")

    set_conf_option(manila_conf, "DEFAULT", "enabled_share_backends", "lvm")
    set_conf_option(manila_conf, "DEFAULT", "enabled_share_protocols", enabled_share_protocols)

    set_conf_option(manila_conf, "lvm", "share_backend_name", backend_name)
    set_conf_option(manila_conf, "lvm", "driver_handles_share_servers", str(driver_handles_share_servers))
    set_conf_option(manila_conf, "lvm", "share_driver", "manila.share.drivers.lvm.LVMShareDriver")
    set_conf_option(manila_conf, "lvm", "lvm_share_volume_group", vg_name)
    set_conf_option(manila_conf, "lvm", "lvm_share_export_ips", share_export_ip)

    try:
        shutil.copy2(MANILA_LVM_NETWORK_SERVICE, SERVICE_PATH)

        with open(MANILA_BRIDGE_IP_SCRIPT, "r") as f:
            template = f.read()
            ip_script_content = template.format(
                PUBLIC_BRIDGE=public_bridge,
                IP_CIDR=f"{share_export_ip}/{public_cidr.split('/')[1]}"
            )

        with open(script_path, "w") as f:
            f.write(ip_script_content)

        os.chmod(script_path, 0o755)

    except Exception as e:
        print(f"\n{colors.RED}Failed to write '{script_path}' with an unhandled exception: {e}{colors.RESET}")
        return False

    return True
    
def finalize(env):

    print()

    if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

    if not run_command(["systemctl", "enable", "--now", "manila-lvm-network.service"], "Enabling Manila LVM Network service..."): return False

    print()

    sudoers_content = "manila ALL=(root) NOPASSWD: /usr/bin/privsep-helper\n"

    with open("/etc/sudoers.d/manila-privsep", "w") as f:
        f.write(sudoers_content)

    os.chmod("/etc/sudoers.d/manila-privsep", 0o440)

    if not run_command(["systemctl", "restart", "manila-share", "manila-lvm-network"], "Restarting Manila Share services...", False, None, 3, 5):
        return False
    
    if not wait_manila_backend(env=env) : return False

    return True

def finalize_lvm_backend(config, env):

    print()

    backend_name = get(config, "manila.backends.lvm.BACKEND_NAME").lower()
    shares = get(config, "manila.shares") or []

    share_type_list = json.loads(os_run_output(["openstack", "share", "type", "list", "-f", "json"], env=env) or "[]")

    default_share_type_exists = any(share_type.get("Name", share_type.get("name")) == "default_share_type" for share_type in share_type_list)

    if not default_share_type_exists:
        if not os_run(["openstack", "share", "type", "create", "default_share_type", "False", "--extra-specs", f"share_backend_name={backend_name}"], "Creating default share type...", env=env):
            return False

    share_list = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env) or "[]")

    for share in shares:
        share_name = share["name"]
        share_type = share.get("share_type", "default_share_type")
        share_protocol = share["share_protocol"]
        share_size = share["share_size"]

        existing_share = next((item for item in share_list if item.get("Name", item.get("name")) == share_name), None)

        if existing_share:
            print(f"{colors.YELLOW}{share_name} already exists, checking status...{colors.RESET}")
            share_id = existing_share.get("ID", existing_share.get("id"))
        else:
            if not os_run(["openstack", "share", "create", "--name", share_name, "--share-type", share_type, share_protocol, str(share_size)], f"Creating share '{share_name}'...", env=env):
                return False

            share_info = wait_share_available(share_name, env)

            if not share_info:
                return False

            share_id = share_info.get("id")

        if not share_id:
            print(f"{colors.RED}ERROR: unable to retrieve {share_name} id{colors.RESET}")
            return False

        export_path = None

        for _ in range(10):
            share_info = json.loads(os_run_output(["openstack", "share", "show", share_id, "-f", "json"], env=env) or "{}")
            export_locations = share_info.get("export_locations", "")

            if export_locations:
                if isinstance(export_locations, str):
                    for line in export_locations.splitlines():
                        if line.strip().startswith("path ="):
                            export_path = line.split("=", 1)[1].strip()
                            break

                elif isinstance(export_locations, list):
                    first_location = export_locations[0]

                    if isinstance(first_location, dict):
                        export_path = first_location.get("path")
                    elif isinstance(first_location, str):
                        export_path = first_location

                if export_path:
                    break

            time.sleep(3)

        if not export_path:
            print(f"{colors.RED}ERROR: {share_name} has no export location available{colors.RESET}")
            return False
        
        print()

        for rule in share.get("access_rules", []):
            rule_access_type = rule["type"]
            rule_access = rule["access"]
            rule_access_level = rule["level"]

            access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")

            rule_exists = any(access.get("access_type", access.get("Access Type")) == rule_access_type and access.get("access_to", access.get("Access To")) == rule_access for access in access_list)

            if rule_exists:
                print(f"{colors.YELLOW}Access rule {rule_access} already exists, skipping creation.{colors.RESET}")
                continue

            if not os_run(["openstack", "share", "access", "create", "--access-level", rule_access_level, share_id, rule_access_type, rule_access], f"Adding access rule {rule_access} to '{share_name}'...", env=env):
                return False

            for _ in range(10):
                access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")

                if any(access.get("access_type", access.get("Access Type")) == rule_access_type and access.get("access_to", access.get("Access To")) == rule_access for access in access_list):
                    break

                time.sleep(2)
            else:
                print(f"\n{colors.RED}ERROR: access rule {rule_access} is not created{colors.RESET}")
                return False

    return True

def run_setup_lvm_backend(config, env):

    lvm_image_file_path = get(config, "manila.backends.lvm.MANILA_LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "manila.backends.lvm.MANILA_LVM_LOOP_PATH")

    vg_name = get(config, "manila.backends.lvm.SHARE_VOLUME_GROUP")


    if not install_pkgs(): return False

    if not conf_lvm(config): return False

    using_loopback = not get(config, "manila.backends.lvm.PHYSICAL_VOLUME")

    if using_loopback:
        if not write_loopback_lvm_env("manila", lvm_image_file_path, lvm_loop_dev, vg_name, description="Manila Loopback LVM", before_services="manila-share.service"): return False   
        if not setup_loopback_service(lvm_image_file_path, lvm_loop_dev, vg_name, "manila"): return False   

    if not conf_lvm_manila(config): return False

    if not finalize(env): return False
    if not finalize_lvm_backend(config, env=env): return False

    return True