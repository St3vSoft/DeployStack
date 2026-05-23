import subprocess
import time
import sys
import json

from ...shell import _run, is_uuid, logger
from ....utils.core import colors

def get_volume_name_from_uuid(uuid) -> str:

    get_volume_name_cmd = [
        "openstack", "volume", "show", uuid, "-f", "value", "-c", "name"
    ]

    try:
        result = subprocess.run(get_volume_name_cmd, capture_output=True, text=True, check=True)

        volume_name = result.stdout.strip()

        if volume_name != "":
            return volume_name
        else:
            logger.error(f"{colors.RED}Error: image name '{uuid}' returned empty name{colors.RESET}\n")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to getting image name: {e}{colors.RESET}\n")
        sys.exit(1)

def get_volume_id_from_name(name) -> str:

    get_volume_id_cmd = [
        "openstack", "volume", "show", name, "-f", "value", "-c", "ID"
    ]

    try:
        result = subprocess.run(get_volume_id_cmd, capture_output=True, text=True, check=True)

        volume_id = result.stdout.strip()

        if volume_id != "":
            return volume_id
        else:
            logger.error(f"{colors.RED}Error: volume name '{name}' returned empty ID{colors.RESET}\n")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to getting volume ID: {e}{colors.RESET}\n")
        sys.exit(1)

def check_volume_attached(volume: str):
    cmd = [
        "openstack", "volume", "show", volume,
        "-f", "json", "-c", "attachments"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        attachments = json.loads(result.stdout)["attachments"]

        if attachments:
            attached_to = ", ".join(a['server_id'] for a in attachments)
            logger.warning(f"{colors.YELLOW}Volume '{volume}' is attached to instance(s): {attached_to}{colors.RESET}\n")
            sys.exit(1)
        else:
            return
        
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to list volume info: {e}\n{e.stderr}{colors.RESET}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"{colors.RED}Failed to parse JSON output: {e}{colors.RESET}")
        sys.exit(1)

def check_image_running_instances(identifier: str) -> bool:

    check_images_instances_cmd = [
        "openstack", "server", "list", "-f", "value", "-c", "Image"
    ]

    try:
        image_name = identifier if not is_uuid(identifier) else get_volume_name_from_uuid(identifier)

        result = subprocess.run(check_images_instances_cmd, capture_output=True, text=True, check=True)
        running_image_names = [line.strip().lower() for line in result.stdout.splitlines()]

        return image_name.lower() in running_image_names
        
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to listing images: {e}{colors.RESET}\n")
        sys.exit(1)

def remove_volume(identifier: str, timeout: int = 30) -> bool:
    remove_volume_cmd = ["openstack", "volume", "delete", identifier]

    try:
        _run(remove_volume_cmd, True)
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to delete volume: {e}{colors.RESET}\n")
        return False

    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        remaining = timeout - elapsed
        if remaining <= 0:
            logger.error(f"{colors.RED}Timeout: image {identifier} was not deleted.{colors.RESET}\n")
            return False

        try:
            result = subprocess.run(
                ["openstack", "volume", "list", "-f", "value", "-c", "ID"],
                capture_output=True,
                text=True,
                check=True
            )
            volume_ids = result.stdout.splitlines()
            if identifier not in volume_ids:
                return True

            logger.info(f"Waiting for volume {identifier} to be deleted...")
        except subprocess.CalledProcessError:
            pass

        time.sleep(min(2, remaining))

def remove(
        volume: str,
        timeout: int
):
    
    volume_id = volume if is_uuid(volume) else get_volume_id_from_name(volume)
    
    volume_identifier = volume_id

    check_volume_attached(volume_identifier)

    print(f"Removing volume '{volume}' ...\n")

    if remove_volume(volume_identifier, timeout):
        print(f"{colors.GREEN}Volume '{volume}' successfully deleted{colors.RESET}")
    else:
        sys.exit(1)

    

    
