import subprocess
import sys
import time

from ....utils.core import colors

from ...shell import logger

def wait_for_volume(volume_name, timeout=300):
    start = time.time()
    while True:
        result = subprocess.run(
            ["openstack", "volume", "show", volume_name, "-f", "value", "-c", "status"],
            capture_output=True, text=True
        )
        status = result.stdout.strip()
        print(f"\rWaiting for volume '{volume_name}' to become available: {status}\033[K", end="")
        if status.lower() == "available":
            break
        if time.time() - start > timeout:
            raise TimeoutError(f"Volume {volume_name} did not become available in {timeout} seconds")
        time.sleep(5)
    print()

def mark_as_bootable(volume_id: str, timeout: int = 300):
    set_bootable_cmd = [
        "openstack", "volume", "set",
        "--bootable", volume_id
    ]

    try:
        subprocess.run(set_bootable_cmd, capture_output=True, text=True, check=True)
        logger.info(f"{colors.GREEN}Volume {volume_id} marked as bootable command sent.{colors.RESET}")
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error sending bootable command: {e}{colors.RESET}")
        sys.exit(1)

    start = time.time()
    while True:
        result = subprocess.run(
            ["openstack", "volume", "show", volume_id, "-f", "value", "-c", "bootable", "-c", "status"],
            capture_output=True, text=True
        )
        output = result.stdout.strip().split()
        if len(output) >= 2:
            bootable_status, vol_status = output
        else:
            bootable_status, vol_status = "False", "unknown"

        print(f"\rWaiting for volume '{volume_id}' to be bootable: {bootable_status} (status: {vol_status})", end="")

        if bootable_status.lower() == "true" and vol_status.lower() == "available":
            break

        if time.time() - start > timeout:
            raise TimeoutError(f"Volume {volume_id} did not become bootable in {timeout} seconds")

        time.sleep(5)

    print()
    logger.info(f"{colors.GREEN}Volume {volume_id} is now bootable and ready.{colors.RESET}")
    

def create_volume(name: str, size: int, source_type: str = None, source_name_or_id: str = None, timeout = 300) -> str:

    size_str = str(size)

    if source_type:
        cmd = [
            "openstack", "volume", "create",
            "--size", size_str,
            f"--{source_type}", source_name_or_id,
            name,
            "-f", "value", "-c", "id"
        ]
    else:
        cmd = [
            "openstack", "volume", "create",
            "--size", size_str,
            name,
            "-f", "value", "-c", "id"
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        volume_id = result.stdout.strip()

        wait_for_volume(volume_id, timeout)

        return volume_id
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to create volume: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)


def create(
    volume_name: str,
    volume_size: int,
    is_bootable: bool,
    image: str = None,
    backup: str = None,
    snapshot: str = None,
    timeout: int = 300
) -> None:

    source_type = None
    source_value = None

    if image:
        source_type = "image"
        source_value = image
    elif backup:
        source_type = "backup"
        source_value = backup
    elif snapshot:
        source_type = "snapshot"
        source_value = snapshot

    mark_bootable_flag = is_bootable

    if source_type:
        print(
            f"Creating volume '{volume_name}' "
            f"from {source_type} '{source_value}'...\n"
        )
    else:
        print(f"Creating empty volume '{volume_name}'...\n")

    volume_id = create_volume(
        volume_name,
        volume_size,
        source_type,
        source_value,
        timeout
    )

    if mark_bootable_flag:
        print("Marking volume as bootable ...\n")
        mark_as_bootable(volume_id, timeout)

    print(
        f"{colors.GREEN}\nVolume '{volume_name}' "
        f"(ID: {volume_id}) successfully created!{colors.RESET}"
    )