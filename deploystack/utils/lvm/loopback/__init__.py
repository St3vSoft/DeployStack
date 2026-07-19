import os
import re

from ....utils.core.commands import run_command
from ....utils.core import colors
from ....templates import LOOPBACK_SERVICE, LOOPBACK_START_SCRIPT, LOOPBACK_STOP_SCRIPT, LVM_ENV_CONF

lvm_conf_path = "/etc/lvm/lvm.conf"

def set_lvm_filter(devices):
    
    filters = [f"a|{dev}|" for dev in devices] + ["r|.*|"]
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

def write_loopback_lvm_env(service, lvm_image_file, lvm_loop_dev, vg_name, description, before_services):

    env_path = f"/etc/default/{service}-lvm"
    SERVICE_PATH = f"/etc/systemd/system/{service}-loopback.service"

    try:

        with open(LOOPBACK_SERVICE, "r") as f:
            template = f.read()
            loopback_service_content = template.format(
                description=description,
                before_services=before_services,
                service=service
            )

        with open(LVM_ENV_CONF, "r") as f:
                template = f.read()
                loopback_env_conf_content = template.format(
                    lvm_loop_dev=lvm_loop_dev, 
                    lvm_image_file=lvm_image_file,
                    vg_name=vg_name
                )

        with open(env_path, "w") as f:
                f.write(loopback_env_conf_content)

        with open(SERVICE_PATH, "w") as f:
            f.write(loopback_service_content)

    except Exception as e:
        print(f"\n{colors.RED}Failed to write '{env_path}' with an unhandled exception: {e}{colors.RESET}")
        return False

    return True

def setup_loopback_service(lvm_image_file_path, lvm_loop_dev, vg_name, service):

    print()

    try:

        with open(LOOPBACK_START_SCRIPT, "r") as f:
            template = f.read()
            cinder_loopback_service_start_script_content = template.format(
                lvm_loop_dev=lvm_loop_dev,
                lvm_image_file_path=lvm_image_file_path,
                VG_NAME=vg_name
            )

        with open(LOOPBACK_STOP_SCRIPT, "r") as f:
            template = f.read()
            cinder_loopback_service_stop_script_content = template.format(
                lvm_loop_dev=lvm_loop_dev,
                lvm_image_file_path=lvm_image_file_path,
                VG_NAME=vg_name
            )

        for path, content in [
            (f"/usr/local/bin/{service}-loopback-start.sh", cinder_loopback_service_start_script_content),
            (f"/usr/local/bin/{service}-loopback-stop.sh", cinder_loopback_service_stop_script_content),
            ]:
            with open(path, "w") as f:
                f.write(content)

            os.chmod(path, 0o755)

    except Exception as e:
        print(f"{colors.RED}Failed to write service files with an unhandled exception: {e}{colors.RESET}")
        return False

    if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

    if not run_command(["systemctl", "enable", "--now", f"{service}-loopback.service"], f"Enabling and starting {service}-loopback service..."): return False

    return True