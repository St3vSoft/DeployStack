import os
import re
import subprocess

from ....utils.core.commands import run_command
from ....utils.core import colors
from ....templates import LOOPBACK_SERVICE

lvm_conf_path = "/etc/lvm/lvm.conf"

def get_root_and_active_lvm_devices():
    system_devices = set()
 
    try:
        root_dev = subprocess.check_output(["findmnt", "-n", "-o", "SOURCE", "/"], text=True).strip()
        
        if "mapper" in root_dev or "loop" in root_dev:

            pkname = subprocess.check_output(["lsblk", "-no", "PKNAME", root_dev], text=True).strip()

            for dev in pkname.splitlines():
                if dev:
                    system_devices.add(f"/dev/{dev}.*")
        else:
            system_devices.add(f"{root_dev}.*")
            
    except Exception as e:
        print(f"{colors.YELLOW}Warning: Unable to detect root device:{e}{colors.RESET}")

    if os.path.exists("/dev/sda"):
        system_devices.add("/dev/sda.*")
        
    return list(system_devices)

def set_lvm_filter(devices):

    system_devices = get_root_and_active_lvm_devices()

    all_allowed_devices = devices + system_devices

    filters = [f"a|{dev}|" for dev in all_allowed_devices] + ["r|.*|"]
    filter_value = '[ ' + ', '.join(f'"{f}"' for f in filters) + ' ]'

    try:
        with open(lvm_conf_path, "r") as f:
            content = f.read()
    except OSError as e:
        print(f"{colors.RED}Error: Unable to read {lvm_conf_path}: {e}{colors.RESET}")
        return False

    devices_match = re.search(r'^(\s*)devices\s*{', content, flags=re.MULTILINE)
    if not devices_match:
        print(f"{colors.RED}Error: No devices section found in lvm.conf{colors.RESET}")
        return False

    section_start = devices_match.end()
    base_indent = devices_match.group(1)

    depth = 1
    pos = section_start
    while pos < len(content) and depth > 0:
        if content[pos] == '{':
            depth += 1
        elif content[pos] == '}':
            depth -= 1
        pos += 1
    section_end = pos - 1
    section_content = content[section_start:section_end]

    filter_pattern = r'^([ \t]*)#?[ \t]*filter\s*=\s*.*$'
    filter_match = re.search(filter_pattern, section_content, flags=re.MULTILINE)

    if filter_match:
        line_indent = filter_match.group(1)
        new_line = f"{line_indent}filter = {filter_value}"
        new_section_content = (
            section_content[:filter_match.start()]
            + new_line
            + section_content[filter_match.end():]
        )
    else:
        pad = base_indent + "    "
        new_section_content = f"\n{pad}filter = {filter_value}\n" + section_content

    new_content = content[:section_start] + new_section_content + content[section_end:]

    if new_content == content:
        return True

    try:
        with open(lvm_conf_path, "w") as f:
            f.write(new_content)
    except OSError as e:
        print(f"{colors.RED}Error: Unable to write {lvm_conf_path}: {e}{colors.RESET}")
        return False

    return True

def write_loopback_lvm_env(service, backend, description, before_services):

    SERVICE_PATH = f"/etc/systemd/system/{service}-loopback.service"

    try:

        with open(LOOPBACK_SERVICE, "r") as f:
            template = f.read()
            loopback_service_content = template.format(
                description=description,
                backend_name=backend,
                before_services=before_services,
                service=service
            )

        with open(SERVICE_PATH, "w") as f:
            f.write(loopback_service_content)

    except Exception as e:
        print(f"\n{colors.RED}Failed to write '{LOOPBACK_SERVICE}' with an unhandled exception: {e}{colors.RESET}")
        return False

    return True

def setup_loopback_service(service, backend):

    print()

    if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

    if not run_command(["systemctl", "enable", f"{service}-{backend}-loopback.service"], f"Enabling {service}-{backend}-loopback service..."): return False

    return True