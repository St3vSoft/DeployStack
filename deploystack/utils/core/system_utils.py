
import random
import string
import socket

import subprocess
import sys
import os

from time import sleep, time

from ...utils.core import colors
from ...utils.config.parser import get

def is_package_installed(package_name: str) -> bool:

    try:

        result = subprocess.run(["dpkg", "-s", package_name], 
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
        )

        return result.returncode == 0
    except FileNotFoundError:
        return False
    
def is_ubuntu_release(target_version: str) -> bool:

    try:
        with open("/etc/os-release") as f:

            info = {}
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)

                    info[key.upper()] = value.strip('"')

        is_ubuntu = info.get("ID") == "ubuntu" or "ubuntu" in info.get("ID_LIKE", "")
        version_matches = info.get("VERSION_ID") == target_version
        
        return is_ubuntu and version_matches

    except FileNotFoundError:
        return False

def is_debian():
    try:
        with open("/etc/os-release") as f:
            data = f.read().lower()

        for line in data.splitlines():
            if line.startswith("id="):

                id_value = line.split("=")[1].strip().strip('"')
                return id_value == "debian"
        return False
    except FileNotFoundError:
        return False

def iface_exists(iface: str) -> bool:
    result = subprocess.run(["ip", "link", "show", iface],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return result.returncode == 0

def nc_wait(addr: str, port: int, timeout: int = 30) -> bool:

    start_time = time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    while True:
        if sock.connect_ex((addr, port)) == 0:
            sock.close()
            return True
        elif time() - start_time > timeout:
            print(f"\n{colors.RED}ERROR:{colors.RESET} Service at {addr}:{port} did not respond within {timeout} seconds.")
            sock.close()

            sys.exit(1);
            return False
        sleep(1)

def service_exists(service_name):
    result = subprocess.run(["systemctl", "list-unit-files", service_name], capture_output=True, text=True)
    return service_name in result.stdout

def check_ifupdown():
    result = subprocess.run(
        ["dpkg", "-s", "ifupdown"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0

def has_hw_virtualization():
    try:
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read()

        cpu_support = ("vmx" in cpuinfo) or ("svm" in cpuinfo)

        kvm_available = False
        try:
            open("/dev/kvm").close()
            kvm_available = True
        except:
            pass

        return cpu_support and kvm_available

    except:
        return False

def get_free_loop():
    loop = subprocess.check_output(["losetup", "-f"]).decode().strip()
    return loop

def generate_password(length=12):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def build_openstack_env(config):
    env = os.environ.copy()

    ip_address = get(config, "network.HOST_IP")
    admin_password = get(config, "passwords.ADMIN_PASSWORD")

    env.update({
        "OS_USERNAME": "admin",
        "OS_PASSWORD": admin_password,
        "OS_PROJECT_NAME": "admin",
        "OS_USER_DOMAIN_NAME": "Default",
        "OS_PROJECT_DOMAIN_NAME": "Default",
        "OS_AUTH_URL": f"http://{ip_address}:5000/v3",
        "OS_IDENTITY_API_VERSION": "3",
    })

    return env
