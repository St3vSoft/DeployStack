import subprocess
import sys
import json

from ....utils.core import colors

from ...shell import logger, is_uuid

from ..helpers import get_volume_id_from_name, get_instance_id_from_name

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


    print(f"{colors.GREEN}Volume '{volume}' "
          f"(ID: {volume_id}) successfully detached from '{instance}' (ID: {instance_id}) instance{colors.RESET}")

