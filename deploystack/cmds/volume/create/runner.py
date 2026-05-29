import subprocess
import sys

from ....utils.core import colors

from ...shell import logger

def mark_as_bootable(id: str):

    set_bootable_cmd = [
        "openstack", "volume", "set",
        "--bootable", id
    ]

    try:
        subprocess.run(set_bootable_cmd, capture_output=True, text=True, check=True)
        logger.info(f"{colors.GREEN}Volume {id} marked as bootable successfully.{colors.RESET}\n")

    except subprocess.CalledProcessError as e:
            logger.error(f"{colors.RED}Error while trying to setting bootable attribute on volume: {e}{colors.RESET}")
            sys.exit(1)
    

def create_volume(name: str, size: int, source_type: str = None, source_name_or_id: str = None) -> str:

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
    snapshot: str = None
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
        source_value
    )

    if mark_bootable_flag:
        print("Marking volume as bootable ...\n")
        mark_as_bootable(volume_id)

    print(
        f"{colors.GREEN}Volume '{volume_name}' "
        f"(ID: {volume_id}) successfully created!{colors.RESET}"
    )