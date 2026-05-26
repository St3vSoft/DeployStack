import subprocess
import sys
import json

from ....utils.core import colors

from ...shell import logger, is_uuid

def get_volume_id_from_name(volume_name:str ) -> str:

    volume_show_info_cmd = [
        "openstack", "volume", "show",
        volume_name, "-f", "value", "-c", "id"
    ]

    try:
        result = subprocess.run(volume_show_info_cmd, capture_output=True, text=True, check=True)

        volume_id = result.stdout.strip()
        return volume_id
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to list volume info: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)

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
    
    if volume_already_attached(instance, volume):
        logger.warning(
            f"{colors.YELLOW}Volume '{volume}' is already attached to instance '{instance}'. No action will be taken.{colors.RESET}"
        )
        sys.exit(1)
    
    print(f"Attaching the volume '{volume}' to instance '{instance}' ...\n")

    attach_volume(volume, instance)

    print(f"{colors.GREEN}Volume '{volume}' successfully attached to '{instance}' Instance{colors.RESET}")

