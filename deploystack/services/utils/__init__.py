import re

from ...utils.core.commands import run_command_output
from ...utils.core.system_utils import is_ubuntu_release
from ...utils.config.parser import get

DEFAULT_UBUNTU_OPENSTACK_RELEASES = {
    "20.04": "ussuri",
    "22.04": "yoga",
    "24.04": "caracal",
    "26.04": "gazpacho",
}


def get_base_host(config):
    ip = config.get("network", {}).get("HOST_IP")
    domain = config.get("network", {}).get("HOST_DOMAIN") or None
    return domain or ip

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


def validate_os_release_available(
    release_name: str,
    package_name: str = "keystone",
) -> bool:
    release_name = release_name.strip().lower()

    for ubuntu_release, openstack_release in DEFAULT_UBUNTU_OPENSTACK_RELEASES.items():
        if is_ubuntu_release(ubuntu_release):
            if openstack_release == release_name:
                return bool(_get_candidate_version(package_name))

    candidate_version = _get_candidate_version(package_name)
    if not candidate_version:
        return False

    try:
        madison_output = run_command_output(["apt-cache", "madison", package_name])
    except Exception as exc:
        return _validate_via_policy(package_name, release_name, candidate_version)

    if not madison_output.strip():
        return _validate_via_policy(package_name, release_name, candidate_version)

    for line in madison_output.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue

        line_version = parts[1]
        source = parts[2]

        if line_version != candidate_version:
            continue

        if re.search(rf"/{re.escape(release_name)}/", source, re.IGNORECASE):
            return True

    return False


def _validate_via_policy(
    package_name: str,
    release_name: str,
    candidate_version: str,
) -> bool:
    try:
        policy_output = run_command_output(["apt-cache", "policy", package_name])
    except Exception as exc:
        return False

    table_match = re.search(r"Version table:\s*\n(?P<table>.*)", policy_output, re.DOTALL)
    version_table = table_match.group("table") if table_match else policy_output

    blocks = re.split(r"^(?=\s*\S+\s+\d+\s*$)", version_table, flags=re.MULTILINE)

    for block in blocks:
        header_match = re.match(r"\s*(?P<version>\S+)\s+\d+\s*$", block, re.MULTILINE)
        if not header_match or header_match.group("version") != candidate_version:
            continue

        source_lines = re.findall(r"^\s*\d+\s+(?P<source>\S.*)$", block, re.MULTILINE)
        for source in source_lines:
            if re.search(rf"/{re.escape(release_name)}/", source, re.IGNORECASE):
                return True

    return False

def is_os_release(config, release):
    os_release = get(config, "openstack.OPENSTACK_RELEASE").lower()
    return os_release == release and validate_os_release_available(release)
