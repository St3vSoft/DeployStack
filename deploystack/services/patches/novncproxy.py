import os

from ...utils.core.commands import run_command
from ...utils.apt.apt import apt_install, apt_update
from ...utils.config.setter import set_service_option

from ...utils.core.system_utils import is_package_installed

venv_path = "/opt/nova-novncproxy-venv"
novncproxy_systemd_unit = "/usr/lib/systemd/system/nova-novncproxy.service"

def add_deadsnaker_ppa():

    if not apt_update() : return False

    print()

    if not is_package_installed("software-properties-common"):
        if not apt_install(["software-properties-common"], "Installing Software Properties Common packages...") : return False

        print()

    if not run_command(["add-apt-repository", "ppa:deadsnakes/ppa", "-y"], "Adding deadsnakes repository...") : return False

    return True

def install_python312():

    print()

    if not apt_install(["python3.12", "python3.12-venv"], "Installing Python3.12 packages...") : return False

    return True

def create_virtual_env():

    print()

    if not run_command(["python3.12", "-m", "venv", venv_path], "Creating novncproxy venv in /opt...") : return False 

    return True

def install_novncproxy(os_release):

    print()

    nova_version = None

    if os_release=="gazpacho":
        nova_version = "33.0.0"

    install_novncproxy_cmd_pip = [os.path.join(venv_path, "bin", "pip"), "install", f"nova=={nova_version}", "eventlet", "websockify", "pymysql"]
    downgrade_cryptography_cmd_pip = [os.path.join(venv_path, "bin", "pip"), "install", "cryptography<43.0", "--force-reinstall"]

    if not run_command(install_novncproxy_cmd_pip, "Installing dependecies in venv...") : return False
    if not run_command(downgrade_cryptography_cmd_pip, "Downgrading Cryptography...") : return False

    return True

def patch_novncproxy_systemd_unit():

    novncproxy_binary_path = os.path.join(venv_path, "bin", "nova-novncproxy")

    set_service_option(novncproxy_systemd_unit, "Service", "ExecStart", f"{novncproxy_binary_path} --config-file=/etc/nova/nova.conf --log-file=/var/log/nova/nova-novncproxy.log")

    print()

    if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

def run_novncproxy_setup_patches(os_release):

    if not add_deadsnaker_ppa() : return False
    if not install_python312() : return False
    if not create_virtual_env() : return False
    if not install_novncproxy(os_release) : return False

    patch_novncproxy_systemd_unit()

    return True







