import subprocess
import sys
import json

from ...utils.core import colors

from ..shell import logger, is_uuid

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