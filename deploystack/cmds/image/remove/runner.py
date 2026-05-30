import subprocess
import time
import sys

from ...shell import _run, is_uuid, logger
from ....utils.core import colors

def get_image_name_from_uuid(uuid) -> str:

    get_image_name_cmd = [
        "openstack", "image", "show", uuid, "-f", "value", "-c", "name"
    ]

    try:
        result = subprocess.run(get_image_name_cmd, capture_output=True, text=True, check=True)

        image_name = result.stdout.strip()

        if image_name != "":
            return image_name
        else:
            logger.error(f"{colors.RED}Error: image name '{uuid}' returned empty name{colors.RESET}\n")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to getting image name: {e}{colors.RESET}\n")
        sys.exit(1)

def get_image_id_from_name(name) -> str:

    get_image_id_cmd = [
        "openstack", "image", "show", name, "-f", "value", "-c", "id"
    ]

    try:
        result = subprocess.run(get_image_id_cmd, capture_output=True, text=True, check=True)

        image_id = result.stdout.strip()

        if image_id != "":
            return image_id
        else:
            logger.error(f"{colors.RED}Error: image name '{name}' returned empty ID{colors.RESET}\n")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to getting image ID: {e}{colors.RESET}\n")
        sys.exit(1)

def check_image_running_instances(identifier: str) -> bool:

    check_images_instances_cmd = [
        "openstack", "server", "list", "-f", "value", "-c", "Image"
    ]

    try:
        image_name = identifier if not is_uuid(identifier) else get_image_name_from_uuid(identifier)

        result = subprocess.run(check_images_instances_cmd, capture_output=True, text=True, check=True)
        running_image_names = [line.strip().lower() for line in result.stdout.splitlines()]

        return image_name.lower() in running_image_names
        
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to listing images: {e}{colors.RESET}\n")
        sys.exit(1)


def remove_glance_image(identifier: str, timeout: int = 30) -> bool:
    remove_image_cmd = ["openstack", "image", "delete", identifier]

    try:
        _run(remove_image_cmd, True)
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to delete image: {e}{colors.RESET}\n")
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
                ["openstack", "image", "list", "-f", "value", "-c", "id"],
                capture_output=True,
                text=True,
                check=True
            )
            image_ids = result.stdout.splitlines()
            if identifier not in image_ids:
                return True

            logger.info(f"Waiting for image {identifier} to be deleted...")
        except subprocess.CalledProcessError:
            pass

        time.sleep(min(2, remaining))

def remove_image(
        image: str,
        timeout: int
):
    
    image_id = image if is_uuid(image) else get_image_id_from_name(image)
    
    image_identifier = image_id
    print(f"Removing image with Name: {image} ...")

    if check_image_running_instances(image_identifier):
        print(f"\n{colors.RED}Error: There are instances still running with the '{image}' image. Please terminate them before attempting removal.{colors.RESET}")
        sys.exit(1)

    if remove_glance_image(image_identifier, timeout):
        print(f"\n{colors.GREEN}Image '{image}' successfully deleted{colors.RESET}")
    else:
        sys.exit(1)

    

    
