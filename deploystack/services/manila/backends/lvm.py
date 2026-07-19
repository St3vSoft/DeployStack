# Configure the LVM Backend (Share Node)

import os
import json
import pwd
import grp
import os
import subprocess
import shutil

from ....utils.core.commands import run_command, os_run_output, os_run
from ....utils.apt.apt import apt_install
from ....utils.config.parser import get
from ....utils.config.setter import set_conf_option

from ....utils.lvm.loopback import write_loopback_lvm_env, setup_loopback_service
from ....utils.lvm import get_vg_for_pv, ensure_system_user_with_run_command

from ....templates import MANILA_LVM_NETWORK_SERVICE, MANILA_BRIDGE_IP_SCRIPT

from ....utils.core import colors

manila_conf = "/etc/manila/manila.conf"

def install_pkgs():

    print()

    if not apt_install(["manila-share", "lvm2", "nfs-kernel-server"], "Installing Manila Share LVM Packages..."):
        return False
    
    return True

def conf_lvm(config):

    lvm_physical_volume = get(config, "manila.lvm.PHYSICAL_VOLUME")
    lvm_image_file_path = get(config, "manila.lvm.LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "manila.lvm.LVM_LOOP_PATH")
    lvm_image_size_in_gb = get(config, "manila.lvm.LVM_IMAGE_SIZE_IN_GB")

    vg_name = get(config, "manila.lvm.SHARE_VOLUME_GROUP")

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

        if lvm_loop_dev not in losetup_output:
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

    backend_name = get(config, "manila.lvm.BACKEND_NAME")

    protocols = get(config, "manila.SHARE_PROTOCOLS", default=["NFS"])
    enabled_share_protocols = ",".join(protocols)

    vg_name = get(config, "manila.lvm.SHARE_VOLUME_GROUP")
    
    public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")
    public_cidr = get(config, "neutron.public_network.PUBLIC_SUBNET_CIDR")

    share_export_ip = get(config, "manila.lvm.SHARE_EXPORT_IP")

    set_conf_option(manila_conf, "DEFAULT", "enabled_share_backends", "lvm")
    set_conf_option(manila_conf, "DEFAULT", "enabled_store_protocols", enabled_share_protocols)

    set_conf_option(manila_conf, "lvm", "share_backend_name", backend_name)
    set_conf_option(manila_conf, "lvm", "driver_handles_share_servers", "False")
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

    except Exception as e:
        print(f"\n{colors.RED}Failed to write '{script_path}' with an unhandled exception: {e}{colors.RESET}")
        return False

    return True
    
def finalize():

    print()

    if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

    if not run_command(["systemctl", "enable", "--now", "manila-lvm-network.service"], "Enabling and starting manila-lvm-network.service..."): return False

    print()

    sudoers_content = "manila ALL=(root) NOPASSWD: /usr/bin/privsep-helper\n"

    with open("/etc/sudoers.d/manila-privsep", "w") as f:
        f.write(sudoers_content)

    os.chmod("/etc/sudoers.d/manila-privsep", 0o440)

    if not run_command(["systemctl", "restart", "manila-share"], "Restarting Manila services..."):
        return False

    return True


def finalize_lvm_backend(env):

    share_type_list = json.loads(os_run_output(["openstack", "share", "type", "list", "-f", "json"], env=env))

    default_share_exists = any(share_type.get("Name") == "default_share_type" for share_type in share_type_list)

    if not default_share_exists:
        print()
        if not os_run([
                "openstack", "share", "type", "create",
                "default_share_type", "False",
                "--extra-specs", "volume_backend_name=LVM"
            ], "Creating default share type...", env=env):
                return False
        
    share_list = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env))

    default_share_exists = any(share.get("Name") == "default_share" for share in share_list)

    if not default_share_exists:
        print()
        if not os_run(["openstack", "share", "create", "NFS", "1", "--name", "default_share"], "Creating default share...", env=env):
            return False
        
    return True
    
def run_setup_lvm_backend(config, env):

    lvm_image_file_path = get(config, "manila.lvm.LVM_IMAGE_FILE_PATH")
    lvm_loop_dev = get(config, "manila.lvm.LVM_LOOP_PATH")

    vg_name = get(config, "manila.lvm.SHARE_VOLUME_GROUP")

    if not install_pkgs(): return False

    if not conf_lvm(config): return False

    using_loopback = not get(config, "manila.lvm.PHYSICAL_VOLUME")

    if using_loopback:
        if not write_loopback_lvm_env("manila", lvm_image_file_path, lvm_loop_dev, vg_name, description="Manila Loopback LVM", before_services="manila-share.service"): return False   
        if not setup_loopback_service(lvm_image_file_path, lvm_loop_dev, vg_name, "manila"): return False   

    if not conf_lvm_manila(config): return False

    if not finalize(): return False
    if not finalize_lvm_backend(env=env): return False

    return True


