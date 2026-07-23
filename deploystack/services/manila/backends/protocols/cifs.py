from .....utils.apt.apt import apt_install, apt_update
from .....utils.core.commands import run_command

def install_pkgs():
    print()

    if not apt_update() : return False

    if not apt_install(["samba", "samba-common-bin"], "Installing Samba CIFS Protocol packages..."):
        return False

    return True

def finalize():

    print()

    if not run_command(["systemctl", "enable", "smbd", "nmbd"], "Enabling Samba services..."):
            return False

    if not run_command(["systemctl", "restart", "smbd", "nmbd"], "Restarting Samba services..."):
        return False

    return True

def run_setup_cifs():

    if not install_pkgs() : return False
    if not finalize(): return False

    return True