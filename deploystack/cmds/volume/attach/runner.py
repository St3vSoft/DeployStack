import subprocess
import sys
import json

from ....utils.core import colors

from ...shell import logger, is_uuid

from ..helpers import get_volume_id_from_name, get_instance_id_from_name

def volume_already_attached(instance: str, volume: str) -> bool:
    cmd = [
        "openstack", "server", "show", instance,
        "-f", "json", "-c", "volumes_attached"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        attached_volumes = json.loads(result.stdout)["volumes_attached"]

        for v in attached_volumes:
            volume_id = v["id"]

            if not is_uuid(volume):
                volume_id_from_name = get_volume_id_from_name(volume)
                volume = volume_id_from_name

            if volume_id == volume:
                return True

        return False

    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to list instance info: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)


def attach_volume(volume: str, instance: str):

    attach_volume_cmd = [
            "openstack", "server", "add",
            "volume", instance, volume
        ]

    try:
        subprocess.run(attach_volume_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to attach volume: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)

def attach(
    volume: str,
    instance: str
):
    
    volume_id = volume if is_uuid(volume) else get_volume_id_from_name(volume)
    instance_id = instance if is_uuid(instance) else get_instance_id_from_name(instance)
    
    if volume_already_attached(instance, volume):
        logger.warning(
            f"{colors.YELLOW}Volume '{volume}' is already attached to instance '{instance}'. No action will be taken.{colors.RESET}"
        )
        sys.exit(1)
    
    print(f"Attaching the volume '{volume}' to instance '{instance}' ...\n")

    attach_volume(volume, instance)

    print(f"{colors.GREEN}Volume '{volume}' "
        f"(ID: {volume_id}) successfully attached from '{instance}' (ID: {instance_id}) instance{colors.RESET}")

