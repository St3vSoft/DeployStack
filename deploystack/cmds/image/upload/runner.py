import requests
import tempfile
import subprocess
import time
import sys
import itertools
import termios
import json
import uuid

import os as os_module

from ....utils.core import colors

from ...shell import _run, _os, logger

from .images import get_image_url

from ....utils.core.system_utils import build_openstack_env_from_session
from ....utils.tasks.check_deployment import internal_admin_openrc_file

OS_ADMIN_USERS = {
    "ubuntu": "ubuntu",
    "debian": "debian",
    "fedora": "fedora",
    "centos": "cloud-user",
    "opensuse": "opensuse",
}

def _has_glance_public_image_permission(env) -> bool:
    image_name = f"permission-check-{uuid.uuid4()}"

    result = _os(
        "image", "create",
        image_name,
        "--disk-format", "raw",
        "--container-format", "bare",
        "--public",
        "-f", "json",
        env=env,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"

    if result.returncode != 0:
        if "You are not authorized to complete publicize_image action" in output:
            return False

        logger.error(
            "Unable to verify Glance public image permission: %s",
            output,
        )
        return False

    try:
        image = json.loads(result.stdout)
        image_id = image["id"]
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.error("Unable to retrieve the temporary image ID: %s", result.stdout)
        return False
    finally:
        pass

    try:
        return True
    finally:
        try:
            _os(
                "image", "delete", image_id,
                env=env,
                check=True,
            )
        except (subprocess.CalledProcessError, SystemExit):
            logger.exception("Failed to delete temporary Glance image %s", image_id)

def _generate_temp_filename(os_name: str, version: str, arch: str, url: str, temp_dir: str = None) -> str:

    ext = os_module.path.splitext(url)[-1]

    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    filename = f"{os_name}-{version}-{arch}{ext}"
    return os_module.path.join(temp_dir, filename)

def _download_image(url: str, output_path: str):

    fd = sys.stdin.fileno()
    old_term = termios.tcgetattr(fd)

    new_term = termios.tcgetattr(fd)
    new_term[3] &= ~termios.ECHO

    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new_term)

        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        chunk_size = 1024 * 1024
        downloaded = 0

        spinner = itertools.cycle(["|", "/", "-", "\\"])

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):

                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    percent = int(downloaded / total_size * 100)
                    spin_char = next(spinner)

                    sys.stdout.write(
                        f"\rDownloading {os_module.path.basename(output_path)}: {percent}% {spin_char}"
                    )

                    sys.stdout.flush()
                    time.sleep(0.1)

        line = f"Downloading {os_module.path.basename(output_path)}: 100%"

        sys.stdout.write("\r" + line + " " * 10 + "\n")
        sys.stdout.flush()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_term)

def _image_already_exists(image_name) -> bool:

    list_images_cmd = [
        "openstack", "image", "list", "-f", "value", "-c", "Name"
    ]

    try:
        result = subprocess.run(list_images_cmd, capture_output=True, text=True, check=True)
        existing_images = [line.strip() for line in result.stdout.splitlines()]

        return image_name in existing_images

    except subprocess.CalledProcessError as e:
        print(f"\n{colors.RED}Error while trying to listing images: {e}{colors.RESET}")
        sys.exit(1)

def _wait_for_image_active(image_name, timeout=300, env=None):
    start = time.time()
    while True:
        result = subprocess.run(
            ["openstack", "image", "show", image_name, "-f", "value", "-c", "status"],
            capture_output=True, text=True, env=env
        )
        status = result.stdout.strip()
        print(f"\rWaiting for image '{image_name}' to become active: {status}", end="")
        if status.lower() == "active":
            break
        if time.time() - start > timeout:
            raise TimeoutError(f"Image {image_name} did not become active in {timeout} seconds")
        time.sleep(5)
    print()

def _upload_image_to_glance(
        filepath: str,
        name: str,
        os: str,
        visibility: str,
        timeout: int,
        env: None
    ) -> bool:
    
    print(f"\nUploading image '{name}' to Glance...\n")

    admin_user = OS_ADMIN_USERS[os]

    create_image_cmd = [
        "openstack", "image", "create",
        "--container-format", "bare",
        "--disk-format", "qcow2",
        "--file", filepath,
        "--property", "os_type=linux",
        "--property", f"os_distro={os}",
        "--property", f"os_admin_user={admin_user}"
    ]

    if visibility == "public":
        create_image_cmd.append("--public")
    elif visibility == "private":
        create_image_cmd.append("--private")
    elif visibility == "shared":
        create_image_cmd.append("--shared")
    elif visibility == "community":
        create_image_cmd.append("--community")

    create_image_cmd.append(name)
    
    try:
        _run(create_image_cmd, env=env)
        _wait_for_image_active(name, timeout, env=env)

        return True
    except subprocess.CalledProcessError as e:
        print(f"{colors.RED}Failed to create image: {e}{colors.RESET}")
        sys.exit(1)
    except TimeoutError as e:
        print(f"{colors.RED}{e}{colors.RESET}")
        sys.exit(1)

def upload_image(
    os: str,
    image_name: str,
    version: str,
    visibility: str,
    output_dir: str,
    keep: bool,
    arch: str,
    timeout: int
):

    image_url = get_image_url(os, version, arch)
    current_session_env = build_openstack_env_from_session()

    glance_image_name: str

    if not _has_glance_public_image_permission(current_session_env):
        print(f"{colors.RED}ERROR: The user '{current_session_env.get('OS_USERNAME')}' does not have permission to make images public on Glance; please try again using a different visibility setting, such as --private, --community, or --shared.{colors.RESET}")
        sys.exit(1)
    
    print("Getting the Download URL for the image...\n")

    if not output_dir:
        output_dir = "/tmp"

    temp_file_path = _generate_temp_filename(os, version, arch, url=image_url, temp_dir=output_dir)

    temp_file_name = os_module.path.splitext(os_module.path.basename(temp_file_path))[0]

    if not image_name:
        glance_image_name = temp_file_name
    else:
        glance_image_name = image_name

    if _image_already_exists(glance_image_name):
        print(f"{colors.RED}Error: Glance image '{glance_image_name}' already exists.{colors.RESET}")
        sys.exit(1)

    _download_image(image_url, temp_file_path)

    if _upload_image_to_glance(temp_file_path, glance_image_name, os, visibility, timeout, env=current_session_env):

        print(f"\n{colors.GREEN}Image successfully uploaded{colors.RESET}")

        if keep:
            print()
            print(f"    The downloaded image is located in the path '{temp_file_path}'\n")

        print(f"    You can now launch instances with the new image uploaded with: deploystack launch --image \"{glance_image_name}\"")

    if not keep:
        os_module.remove(temp_file_path)