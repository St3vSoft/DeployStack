
from pathlib import Path

import re
import os
import subprocess

from ...utils.core.commands import run_command_output, run_command
from ...utils.apt.apt import apt_install
from ...utils.core.system_utils import is_ubuntu_release, is_package_installed
from ...utils.config.parser import get
from ...utils.core import colors

from collections.abc import Sequence

UCA_URL = "http://ubuntu-cloud.archive.canonical.com/ubuntu"

UBUNTU_CLOUD_ARCHIVE = {
    ("jammy", "zed"),
    ("jammy", "antelope"),
    ("jammy", "bobcat"),
    ("jammy", "caracal"),
    ("noble", "dalmatian"),
    ("noble", "epoxy"),
    ("noble", "flamingo"),
    ("noble", "gazpacho"),
    ("resolute", "hibiscus"),
}

UBUNTU_NATIVE_OPENSTACK = {
    "jammy":    "yoga",
    "lunar":    "antelope",
    "mantic":   "bobcat",
    "noble":    "caracal",
    "oracular": "dalmatian",
    "plucky":   "epoxy",
    "questing": "flamingo",
    "resolute": "gazpacho",
    "stonking": "hibiscus",
}

DEFAULT_UBUNTU_OPENSTACK_RELEASES = {
    "22.04": "yoga",
    "22.10": "zed",
    "23.04": "antelope",
    "23.10": "bobcat",
    "24.04": "caracal",
    "24.10": "dalmatian",
    "25.04": "epoxy",
    "25.10": "flamingo",
    "26.04": "gazpacho",
    "26.10": "hibiscus"
}

def _get_candidate_version(package_name: str) -> str | None:

    try:
        policy_output = run_command_output(["apt-cache", "policy", package_name])
    except Exception as exc:
        return None

    if not policy_output or "Unable to locate package" in policy_output:
        return None

    match = re.search(
        r"^\s*Candidate:\s*(?P<version>\S+)\s*$",
        policy_output,
        re.MULTILINE,
    )
    if not match:
        return None

    version = match.group("version")
    return None if version in ("(none)", "") else version

def _source_contains_release(source: str, release_name: str) -> bool:
    return bool(
        re.search(
            rf"(?:^|[-/]){re.escape(release_name)}(?:[-/]|$)",
            source,
            re.IGNORECASE,
        )
    )

def _validate_via_policy(
    package_name: str,
    release_name: str,
    candidate_version: str,
) -> bool:
    try:
        output = run_command_output(
            ["apt-cache", "policy", package_name]
        )
    except Exception:
        return False

    if not isinstance(output, str) or not output:
        return False

    header_re = re.compile(
        r"^\s*(?:\*\*\*\s+)?(?P<version>\S+)\s+\d+\s*$"
    )
    source_re = re.compile(r"^\s+\d+\s+(?P<source>\S.*)$")

    current_version = None

    for line in output.splitlines():
        header = header_re.match(line)

        if header:
            current_version = header.group("version")
            continue

        if current_version != candidate_version:
            continue

        source_match = source_re.match(line)
        if source_match and _source_contains_release(
            source_match.group("source"),
            release_name,
        ):
            return True

    return False

def validate_os_release_available(
    release_name: str | Sequence[str],
    package_name: str = "keystone",
) -> bool:

    if isinstance(release_name, str):
        release_names = [release_name]
    elif isinstance(release_name, Sequence):
        release_names = list(release_name)
    else:
        return False

    release_names = [
        name.strip().lower()
        for name in release_names
        if isinstance(name, str) and name.strip()
    ]

    if not release_names:
        return False

    candidate_version = _get_candidate_version(package_name)
    if not candidate_version:
        return False

    # Native OpenStack release for the current Ubuntu version.
    for ubuntu_version, openstack_release in (
        DEFAULT_UBUNTU_OPENSTACK_RELEASES.items()):
        if (is_ubuntu_release(ubuntu_version) and openstack_release in release_names):
            return True

    try:
        output = run_command_output(["apt-cache", "madison", package_name])
    except Exception:
        return any(_validate_via_policy(package_name, release, candidate_version) for release in release_names)

    if not isinstance(output, str) or not output.strip():
        return any(_validate_via_policy(package_name, release, candidate_version) for release in release_names)

    for line in output.splitlines():
        parts = [part.strip() for part in line.split("|", 2)]

        if len(parts) != 3:
            continue

        _, version, source = parts

        if version != candidate_version:
            continue

        if any(_source_contains_release(source, release) for release in release_names):
            return True

    # Try the alternative parser if madison's format did not match.
    return any(_validate_via_policy( package_name, release, candidate_version) for release in release_names)

def ensure_os_release(config, release: str) -> bool:
    configured_release = get(config, "openstack.OPENSTACK_RELEASE")

    if not isinstance(configured_release, str):
        return False

    if not isinstance(release, str):
        return False

    configured_release = configured_release.strip().lower()
    release = release.strip().lower()

    if not configured_release or configured_release != release:
        return False

    return validate_os_release_available(release)

def add_uca_repo(release: str):
    
    result = run_command(["add-apt-repository", "-y", f"cloud-archive:{release}"], f"Adding Ubuntu Cloud Archive repository for {release}...")
    
    if not result:
        return False
    
    return True

def setup_debian_repo(distro_codename: str, release: str):

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

    if not is_package_installed("extrepo"):
        print()
        if not apt_install(["extrepo"], "Installing extrepo Package...") : return False

    available_releases_repos = run_command_output(["extrepo", "search", "openstack"])

    supported_releases = [
        line.removeprefix("Found openstack_").removesuffix(":")
        for line in available_releases_repos.splitlines()
        if line.startswith("Found openstack_")
    ]

    if release not in supported_releases:
        print(f"{colors.RED}ERROR: Unsupported OpenStack release: '{release}'{colors.RESET}")
        print("\nSupported OpenStack releases:")

        for supported_release in supported_releases:
            print(f"  - {supported_release}")

        return False

    if not run_command(["extrepo", "enable", f"openstack_{release}"], f"Enabling OpenStack {release} repo...") : return False

    return True

def enable_cloud_archive(release: str, series: str) -> bool:

    list_file = Path(f"/etc/apt/sources.list.d/cloudarchive-{release}.list")
    line = f"deb {UCA_URL} {series}-updates/{release} main\n"

    if not apt_install(["ubuntu-cloud-keyring"], "Installing Ubuntu Cloud Keyring Package... ") : return False

    if not list_file.exists() or list_file.read_text() != line:
        list_file.write_text(line)

    return True