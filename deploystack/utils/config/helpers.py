import ipaddress
import psutil
import subprocess

from .parser import get
from ..core import colors

def get_provider_networks(config):

    networks_list = get(config, "neutron.provider_networks", [])
    result = []

    for net in networks_list:
        net_info = {
            "bridge": net.get("bridge"),
            "name": net.get("name"),
            "type": net.get("type")
        }
        result.append(net_info)

    return result

def interface_exists(if_name: str) -> bool:
    return if_name in psutil.net_if_addrs()

def validate_ip(value: str, field_name: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        print(f"{colors.RED}Error: '{field_name}' contains an invalid IP: {value}{colors.RESET}")
        return False

def validate_cidr(value: str, field_name: str) -> bool:
    try:
        ipaddress.ip_network(value, strict=False)
        return True
    except ValueError:
        print(f"{colors.RED}Error: '{field_name}' contains an invalid network CIDR: {value}{colors.RESET}")
        return False

def is_loop_device(path: str) -> bool:
    try:
        result = subprocess.run(
            ["lsblk", "-no", "TYPE", path],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip() == "loop"
    except Exception:
        return False