import subprocess
import sys
import json

from ....utils.core import colors

from ...shell import logger, is_uuid

from ..attach.runner import get_volume_id_from_name

def get_instance_id_from_name(instance_name:str ) -> str:

    instance_show_info_cmd = [
        "openstack", "server", "show",
        instance_name, "-f", "value", "-c", "id"
    ]

    try:
        result = subprocess.run(instance_show_info_cmd, capture_output=True, text=True, check=True)

        volume_id = result.stdout.strip()
        return volume_id
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to list instance info: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)

def volume_already_detached(instance: str, volume: str) -> bool:
    cmd = [
        "openstack", "server", "show", instance,
        "-f", "json", "-c", "volumes_attached"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        attached_volumes = json.loads(result.stdout)["volumes_attached"]

        if not is_uuid(volume):
            volume = get_volume_id_from_name(volume)

        for v in attached_volumes:
            if v["id"] == volume:
                return False

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to list instance info: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)


def detach_instance_volume(volume: str, instance: str):

    detach_volume_cmd = [
            "openstack", "server", "remove",
            "volume", instance, volume
        ]

    try:
        subprocess.run(detach_volume_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to detach volume: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)

def reset_volume_state(volume: str):
    """Reset the volume's state to 'available' and its attach status to 'detached'."""

    reset_status_cmd = [
        "openstack", "volume", "set",
        "--state", "available",
        volume
    ]

    reset_attach_cmd = [
        "cinder", "reset-state",
        "--attach-status", "detached",
        volume
    ]

    try:
        subprocess.run(reset_status_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while resetting volume state: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)

    try:
        subprocess.run(reset_attach_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while resetting volume attach status: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)

def mark_volume_deleted(volume_id: str, instance_id: str):
    """
    Marks the volume as deleted in the Nova database for a given instance.
    """

    cmd = [
        "mysql", "-u", "root",
        "-e",
        f"USE nova; UPDATE block_device_mapping SET deleted=1 "
        f"WHERE volume_id='{volume_id}' AND instance_uuid='{instance_id}';"
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"{colors.GREEN}Volume '{volume_id}' marked as removed for instance '{instance_id}' in the database.{colors.RESET}\n")
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while updating the database: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)

def detach(
        volume: str,
        instance: str
):
    
    volume_id = volume if is_uuid(volume) else get_volume_id_from_name(volume)
    instance_id = instance if is_uuid(instance) else get_instance_id_from_name(instance)

    if volume_already_detached(instance_id, volume_id):
        logger.warning(
            f"{colors.YELLOW}Volume '{volume}' is not attached to instance '{instance}'. No action will be taken.{colors.RESET}"
        )
         
        sys.exit(1)

    print(f"Detaching volume '{volume}' on instance '{instance}' ...\n")

    detach_instance_volume(volume_id, instance_id)

    print(f"Resetting volume '{volume}' status ...\n")

    reset_volume_state(volume_id)

    print(f"Marking volume '{volume}' as removed ...\n")

    mark_volume_deleted(volume_id, instance_id)

    print(f"{colors.GREEN}Volume '{volume}' successfully detached from {instance} instance{colors.RESET}")

