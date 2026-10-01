import os

from pathlib import Path

from ...utils.core.commands import run_command
from ...utils.core.system_utils import is_package_installed
from ...utils.apt.apt import apt_install

openstackclient_venv = "/opt/openstackclient-venv"
venv_pip = f"{openstackclient_venv}/bin/pip"

def create_venv_and_install_openstackclient(release):

    if is_package_installed("python3-openstackclient"):
        if not run_command(["apt-get", "remove", "-y", "python3-openstackclient"], "Removing conflicting apt openstackclient...") : return False

    if not is_package_installed("python3-venv"):
        if not apt_install(["python3-venv"], "Installing python3-venv package...") : return False

    if not os.path.exists(openstackclient_venv):
        if not run_command(["python3", "-m", "venv", openstackclient_venv], "Creating venv for OpenStack Client in /opt...") : return False

    if not run_command([venv_pip, "install", "--upgrade", "pip"], "Upgrading pip in venv...") : return False

    print()

    python_openstackclient_version: str

    if release == "gazpacho":
        python_openstackclient_version = "9.0.0"
    elif release == "gazpacho":
        python_openstackclient_version = "8.0.0"

    if not run_command([venv_pip, "install", f"python-openstackclient=={python_openstackclient_version}"], "Installing OpenStack Client in venv...") : return False

    venv_openstack_bin = f"{openstackclient_venv}/bin/openstack"
    system_openstack_link = "/usr/local/bin/openstack"

    target = Path(system_openstack_link)
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(venv_openstack_bin)

    return True