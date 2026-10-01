
from ....utils.core.system_utils import is_package_installed
from ....utils.core.commands import run_command

from ..openstackclient import venv_pip

def install_manilaclient_in_venv(release):

    if is_package_installed("python3-manilaclient"):
        print()
        if not run_command(["apt-get", "remove", "-y", "python3-manilaclient"], "Removing conflicting apt manilaclient...") : return False

    python_manilaclient_version: str

    if release == "gazpacho":
        python_manilaclient_version = "6.0.0"
    elif release == "flamingo":
        python_manilaclient_version = "5.6.0"

    print()

    if not run_command([venv_pip, "install", f"python-manilaclient=={python_manilaclient_version}"], "Installing Manila Client in venv...") : return False

    return True