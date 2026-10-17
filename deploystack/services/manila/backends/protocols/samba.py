import pexpect
import os

import pwd
import grp

from .....utils.apt.apt import apt_install, apt_update
from .....utils.core.commands import run_command
from .....utils.config.setter import set_samba_option

from .....utils.config.parser import get
from .....utils.core.system_utils import service_exists, is_package_installed

from ..utils import user_exists, samba_user_exists, user_in_group
from .....utils.core import colors

smb_conf = "/etc/samba/smb.conf"

def _smbpasswd_add(username, password):
    child = pexpect.spawn(
        f"smbpasswd -a {username}",
        encoding="utf-8",
        timeout=15
    )

    try:
        child.expect("New SMB password:")
        child.sendline(password)

        child.expect("Retype new SMB password:")
        child.sendline(password)

        child.expect(pexpect.EOF)
        child.wait()

        if child.exitstatus != 0:
            print(f"{colors.RED}Error: smbpasswd exited with code {child.exitstatus}{colors.RESET}")
            return False

        return True

    except pexpect.TIMEOUT:
        print(f"{colors.RED}Error: smbpasswd timed out waiting for prompt{colors.RESET}")
        child.terminate()
        return False

    except pexpect.ExceptionPexpect as e:
        print(f"{colors.RED}Error: smbpasswd error: {e}{colors.RESET}")
        return False

def install_pkgs():
    print()

    if not apt_update() : return False

    if not apt_install(["samba", "samba-common-bin"], "Installing Samba CIFS Protocol packages..."):
        return False

    return True

def conf_samba():

    set_samba_option(smb_conf, "global", "include", "registry")

def add_samba_user(config):

    samba_username = get(config, "manila.backends.lvm.samba.SAMBA_SERVER_USER")
    samba_password = get(config, "manila.backends.lvm.samba.SAMBA_SERVER_USER_PASSWORD")

    if not user_exists(samba_username):
        print()

        if not run_command(["useradd", "-m", "-s", "/usr/sbin/nologin", samba_username], "Adding Samba User...") : return False

    if not samba_user_exists(samba_username):
        if not _smbpasswd_add(samba_username, samba_password):
            return False

    if not user_in_group(samba_username, "manila"):
        print()

        if not run_command(["usermod", "-aG", "manila", samba_username], "Adding Samba user to Manila group...") : return False

    return True

def set_filesystems_permissions():

    manila_directories = [
        "/var/lib/manila",
        "/var/lib/manila/mnt"
    ]

    try:
        manila_user = pwd.getpwnam("manila")
        manila_group = grp.getgrnam("manila")

        uid = manila_user.pw_uid
        gid = manila_group.gr_gid

        for directory in manila_directories:
            os.makedirs(directory, exist_ok=True)

            os.chown(directory, uid, gid)
            os.chmod(directory, 0o750)

    except (OSError, KeyError) as e:
        print(
            f"\n{colors.RED}Unable to prepare Manila directory "
            f"{directory}: {e}{colors.RESET}\n"
        )
        return False

    return True

def finalize():

    print()

    samba_services = ["smbd.service"]

    if service_exists("nmbd.service"):
        samba_services.append("nmbd.service")

    if not run_command(["systemctl", "enable"] + samba_services, "Enabling Samba services..."):
            return False

    if not run_command(["systemctl", "restart"] + samba_services, "Restarting Samba services..."):
        return False

    return True

def run_setup_samba(config):

    if not is_package_installed(["samba", "samba-common-bin"]):
        if not install_pkgs() : return False

    conf_samba()

    if not add_samba_user(config): return False

    if not set_filesystems_permissions(): return False

    if not finalize(): return False

    return True