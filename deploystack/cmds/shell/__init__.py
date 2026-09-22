import subprocess
import sys
import logging
import re

logger = logging.getLogger(__name__)

def _run(args: list[str], check=True, env=None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=60, check=check, env=env
        )
    except FileNotFoundError:
        logger.error("'openstack' CLI not found in PATH")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout executing: {' '.join(args)}")
        sys.exit(1)


def _os(*args) -> str:
    result = _run(["openstack"] + list(args))
    return result.stdout.strip()


def _os_value(*args) -> str:
    result = _run(["openstack"] + list(args) + ["-f", "value"])
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""

def is_uuid(identifier) -> bool:
    uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.fullmatch(uuid_regex, identifier.lower()))