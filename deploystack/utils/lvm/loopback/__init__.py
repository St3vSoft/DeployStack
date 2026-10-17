import grp
import os
import pwd

from pathlib import Path

from ....utils.core.commands import run_command, run_command_output
from ....utils.core import colors
from ....templates import LOOPBACK_SERVICE

from ...lvm import ensure_system_user_with_run_command

def create_lvm_loopback_sparse_disk(image_path, image_size, lvm_dev, service_user: str):

    image_path = Path(image_path)
    image_path.parent.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        print()

        truncate_cmd = ["truncate", "-s", f"{image_size}G", str(image_path)]

        if not run_command(truncate_cmd, "Allocating LVM disk image...") : return False

        if not ensure_system_user_with_run_command(service_user) : return False

        uid = pwd.getpwnam(service_user).pw_uid
        gid = grp.getgrnam(service_user).gr_gid

        os.chown(image_path, uid, gid)
        os.chmod(image_path, 0o600)

    try:
        losetup_output = run_command_output(["losetup", "-a"])
    except Exception:
        return False

    if str(image_path) not in losetup_output:
        print()
        
        if not run_command(["losetup", str(lvm_dev), str(image_path)], f"Associating {lvm_dev} to {image_path}..."): return False

    return True

def write_loopback_lvm_env(service, backend, description, before_services):

    SERVICE_PATH = f"/etc/systemd/system/{service}-{backend}-loopback.service"

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