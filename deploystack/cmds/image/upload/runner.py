import requests
import os as os_module
import tempfile
import subprocess
import time
import sys
import itertools

from tqdm import tqdm

from ....utils.core import colors

from ...shell import _run

from .images import get_image_url

OS_ADMIN_USERS = {
    "ubuntu": "ubuntu",
    "debian": "debian",
    "fedora": "fedora",
    "centos": "cloud-user",
    "opensuse": "opensuse",
}

def generate_temp_filename(os_name: str, version: str, arch: str, url: str, temp_dir: str = None) -> str:

    ext = os_module.path.splitext(url)[-1]

    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    filename = f"{os_name}-{version}-{arch}{ext}"
    return os_module.path.join(temp_dir, filename)

def download_image(url: str, output_path: str):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    chunk_size = 1024 * 1024  # 1 MB
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
                time.sleep(0.5)

    sys.stdout.write(
        f"\rDownloading {os_module.path.basename(output_path)}: 100% \n"
    )
    sys.stdout.flush()

def image_already_exists(image_name) -> bool:

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

def wait_for_image(image_name, timeout=300):
    start = time.time()
    while True:
        result = subprocess.run(
            ["openstack", "image", "show", image_name, "-f", "value", "-c", "status"],
            capture_output=True, text=True
        )
        status = result.stdout.strip()
        print(f"\rWaiting for image '{image_name}' to become active: {status}", end="")
        if status.lower() == "active":
            break
        if time.time() - start > timeout:
            raise TimeoutError(f"Image {image_name} did not become active in {timeout} seconds")
        time.sleep(5)
    print()

def upload_glance_image(
        filepath: str,
        name: str,
        os: str,
        visibility: str,
        timeout: int
    ) -> bool:
    
    print(f"\nUploading image '{name}' ...\n")

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

    create_image_cmd.append(f"{name}")
    
    try:
        _run(create_image_cmd)

        wait_for_image(name, timeout)

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
    
    print("Getting the Download URL for the image...\n")
    image_url = get_image_url(os, version, arch)

    if not output_dir:
        output_dir = "/tmp"

    glance_image_name: str

    temp_file_path = generate_temp_filename(os, version, arch, url=image_url, temp_dir=output_dir)

    temp_file_name = os_module.path.splitext(os_module.path.basename(temp_file_path))[0]

    if not image_name:
        glance_image_name = temp_file_name
    else:
        glance_image_name = image_name

    if image_already_exists(glance_image_name):
        print(f"{colors.RED}Error: Glance image '{glance_image_name}' already exists.{colors.RESET}")
        sys.exit(1)

    download_image(image_url, temp_file_path)

    if upload_glance_image(temp_file_path, glance_image_name, os, visibility, timeout):

        print(f"\n{colors.GREEN}Image successfully uploaded{colors.RESET}")

        if keep:
            print()
            print(f"    The downloaded image is located in the path '{temp_file_path}'\n")

        print(f"    You can now launch instances with the new image uploaded with: deploystack launch --image \"{glance_image_name}\"")

    if not keep:
        os_module.remove(temp_file_path)