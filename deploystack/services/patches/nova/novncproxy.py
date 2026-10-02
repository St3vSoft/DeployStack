import os

from ....utils.core.commands import run_command
from ....utils.apt.apt import apt_install, apt_update

from ...utils import ensure_os_release

from ....utils.core.system_utils import is_package_installed

from ....templates import NOVA_NOVNCPROXY_PATCH

novncproxy_dropin_dir = "/etc/systemd/system/nova-novncproxy.service.d"
venv_path = "/opt/nova-novncproxy-venv"

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

def install_novncproxy(config, os_release):

    print()

    nova_version = None

    if os_release == "gazpacho" and ensure_os_release(config, "gazpacho"):
        nova_version = "33.0.0"

    install_novncproxy_cmd_pip = [os.path.join(venv_path, "bin", "pip"), "install", f"nova=={nova_version}", "eventlet", "websockify", "pymysql"]
    downgrade_cryptography_cmd_pip = [os.path.join(venv_path, "bin", "pip"), "install", "cryptography<43.0", "--force-reinstall"]

    if not run_command(install_novncproxy_cmd_pip, "Installing dependecies in venv...") : return False
    if not run_command(downgrade_cryptography_cmd_pip, "Downgrading Cryptography...") : return False

    return True

def patch_novncproxy_systemd_unit():

    novncproxy_binary_path = os.path.join(venv_path, "bin", "nova-novncproxy")
    novncproxy_dropin = os.path.join(novncproxy_dropin_dir, "nova-novncproxy-patch.conf")

    os.makedirs(novncproxy_dropin_dir, exist_ok=True)

    with open(NOVA_NOVNCPROXY_PATCH, "r") as f:
            template = f.read()

    nova_novncproxy_service_content = template.format(
        binary_path=novncproxy_binary_path
    )

    with open(novncproxy_dropin, "w") as f:
        f.write(nova_novncproxy_service_content)

    print()

    if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

    return True

def run_novncproxy_setup_patches(config, os_release):

    if not add_deadsnaker_ppa() : return False
    if not install_python312() : return False
    if not create_virtual_env() : return False
    if not install_novncproxy(config, os_release) : return False

    if not patch_novncproxy_systemd_unit() : return False

    return True