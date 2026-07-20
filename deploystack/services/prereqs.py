import subprocess
import os

from ..utils.core.commands import run_command
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import get
from ..utils.core.system_utils import nc_wait
from ..utils.core import colors

from ..utils.lvm.loopback import set_lvm_filter
from ..utils.config.helpers import parse_bool

UBUNTU_CLOUD_ARCHIVE = {
    ("focal",   "yoga"):      "focal-updates/yoga",
    ("focal",   "zed"):       "focal-updates/zed",
    ("jammy",   "yoga"):      "jammy-updates/yoga",
    ("jammy",   "zed"):       "jammy-updates/zed",
    ("jammy",   "antelope"):  "jammy-updates/antelope",
    ("jammy",   "bobcat"):    "jammy-updates/bobcat",
    ("jammy",   "caracal"):   "jammy-updates/caracal",
    ("noble",   "dalmatian"): "noble-updates/dalmatian",
    ("noble",   "epoxy"):     "noble-updates/epoxy",
    ("noble",   "flamingo"):  "noble-updates/flamingo",
    ("noble",   "gazpacho"):  "noble-updates/gazpacho"
}

UBUNTU_NATIVE_OPENSTACK = {
    "focal":    "ussuri",
    "jammy":    "yoga",
    "lunar":    "antelope",    # 23.04
    "mantic":   "bobcat",      # 23.10
    "noble":    "caracal",     # 24.04
    "oracular": "dalmatian",   # 24.10
    "plucky":   "epoxy",       # 25.04
    "questing": "epoxy",       # 25.10
    "resolute": "gazpacho",    # 26.04
}

def _add_uca_repo(release: str):
    
    result = run_command(
        ["add-apt-repository", "-y", f"cloud-archive:{release}"],
        f"Adding Ubuntu Cloud Archive repository for {release}..."
    )
    
    if not result:
        return False
    
    return True

def _setup_debian_repo(distro_codename: str, release: str):
    dpkg_conf = "/etc/apt/apt.conf.d/90force-conf"
    repo_file = "/etc/apt/sources.list.d/debian-backports.list"
    repo_line = f"deb http://deb.debian.org/debian {distro_codename}-backports main"

    if not os.path.exists(repo_file):
        with open(repo_file, "w") as f:
            f.write(repo_line + "\n")

    subprocess.run(
        'echo "debconf debconf/frontend select Noninteractive" | debconf-set-selections',
        shell=True, check=True
    )
    with open(dpkg_conf, "w") as f:
        f.write('DPkg::Options {"--force-confdef"; "--force-confold"; };')

    print(f"{colors.YELLOW}Debian: OpenStack packages from backports. "
          f"Version '{release}' may not be guaranteed.{colors.RESET}")


UBUNTU_CLOUD_ARCHIVE = {
    ("focal",   "wallaby"),
    ("focal",   "xena"),
    ("focal",   "yoga"),
    ("jammy",   "zed"),
    ("jammy",   "antelope"),
    ("jammy",   "bobcat"),
    ("jammy",   "caracal"),
    ("noble",   "dalmatian"),
    ("noble",   "epoxy"),
    ("noble",   "flamingo"),
    ("noble",   "gazpacho")
}

UBUNTU_NATIVE_OPENSTACK = {
    "focal":    "ussuri",
    "jammy":    "yoga",
    "lunar":    "antelope",
    "mantic":   "bobcat",
    "noble":    "caracal",
    "oracular": "dalmatian",
    "plucky":   "epoxy",
    "questing": "epoxy",
    "resolute": "gazpacho",
}

def set_openstack_release(config):
    release = get(config, "openstack.OPENSTACK_RELEASE", "caracal").lower()

    try:
        distro_id = subprocess.check_output(
            ["lsb_release", "-is"], stderr=subprocess.DEVNULL
        ).decode().strip().lower()
        distro_codename = subprocess.check_output(
            ["lsb_release", "-cs"], stderr=subprocess.DEVNULL
        ).decode().strip().lower()
    except subprocess.CalledProcessError:
        print(f"{colors.RED}Failed to detect Linux distribution{colors.RESET}")
        return False

    if distro_id == "ubuntu":
        native = UBUNTU_NATIVE_OPENSTACK.get(distro_codename)

        if native == release:
            print(f"{colors.GREEN}OpenStack {release} is natively available "
                  f"on Ubuntu {distro_codename}, skipping Cloud Archive.{colors.RESET}")

        elif (distro_codename, release) in UBUNTU_CLOUD_ARCHIVE:
            if not _add_uca_repo(release):
                return False

        else:
            print(f"{colors.RED}OpenStack '{release}' is not supported "
                  f"on Ubuntu '{distro_codename}'.{colors.RESET}")
            _print_supported_combinations(distro_codename, native)
            return False

    elif distro_id == "debian":
        _setup_debian_repo(distro_codename, release)
    else:
        print(f"{colors.YELLOW}Warning: Unknown distribution '{distro_id}'. "
              f"Skipping repository setup.{colors.RESET}")

    if not apt_update():
        return False

    return True

def _print_supported_combinations(current_codename: str, native: str):
    print(f"{colors.YELLOW}Supported combinations:{colors.RESET}")
    for (codename, rel) in sorted(UBUNTU_CLOUD_ARCHIVE):
        marker = " ← you are here" if codename == current_codename else ""
        print(f"  Ubuntu {codename} -> {rel} (via Cloud Archive){marker}")
    if native:
        print(f"  Ubuntu {current_codename} -> {native} (native, no UCA needed)")

def install_pkgs(config):

    print()

    devices = []
    prereqs_pkgs = ["wget", "rabbitmq-server", "python3-openstackclient", "memcached"]

    install_manila = parse_bool(get(config, "optional_services.INSTALL_MANILA", False))
    install_cinder = parse_bool(get(config, "optional_services.INSTALL_CINDER", False))

    is_lvm_manila_backend_enabled = get(config, "manila.BACKEND") == "lvm"

    if install_cinder:
        cinder_pv = get(config, "cinder.lvm.PHYSICAL_VOLUME")
        cinder_loop_dev = get(config, "cinder.lvm.CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_PATH")

        devices.append(cinder_pv or cinder_loop_dev)

    if install_manila and is_lvm_manila_backend_enabled:
        manila_pv = get(config, "manila.backends.lvm.PHYSICAL_VOLUME")
        manila_loop_dev = get(config, "manila.backends.lvm.MANILA_LVM_LOOP_PATH")

        devices.append(manila_pv or manila_loop_dev)
        
    if devices:
        prereqs_pkgs.append("lvm2")

    if not apt_install(prereqs_pkgs, ux_text=f"Installing prerequisite packages..."): return False

    if devices:
        if not set_lvm_filter(devices):
            return False

    return True


def add_rabbitmq_openstack_user(config):
     
    print()

    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")

    try:
        output = subprocess.check_output(["rabbitmqctl", "list_users"], text=True)
        user_exists = "openstack" in output
    except subprocess.CalledProcessError:
        user_exists = False

    if not user_exists:
        if not run_command(
            ["rabbitmqctl", "add_user", "openstack", rabbitmq_password],
            "Creating RabbitMQ OpenStack User..."
        ): return False

    if not run_command(
        ["rabbitmqctl", "set_permissions", "openstack", ".*", ".*", ".*"],
        "Setting permissions for RabbitMQ OpenStack User..."
    ): return False
    
    return True

def run_setup_prereqs(config):

    ip_address = get(config, "network.HOST_IP")

    if not set_openstack_release(config): return False
    if not install_pkgs(config): return False

    if not nc_wait(ip_address, 5672) : return False
    if not add_rabbitmq_openstack_user(config): return False

    print(f"\n{colors.GREEN}Prerequisites configured successfully!{colors.RESET}\n")
    return True