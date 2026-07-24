from .....utils.apt.apt import apt_install, apt_update
from .....utils.core.commands import run_command
from .....utils.core.system_utils import is_package_installed

def install_pkgs():
    print()

    if not apt_update() : return False

    if not apt_install(["nfs-kernel-server", "nfs-common"], "Installing NFS Server packages..."):
        return False

    return True

def finalize():

    print()

    if not run_command(["systemctl", "enable", "nfs-server"], "Enabling NFS service..."):
                return False

    if not run_command(["systemctl", "restart", "nfs-server"], "Restarting NFS service..."):
            return False
    
    return True

def run_setup_nfs():

    if not is_package_installed(["nfs-kernel-server", "nfs-common"]):
        if not install_pkgs() : return False

    if not finalize(): return False

    return True