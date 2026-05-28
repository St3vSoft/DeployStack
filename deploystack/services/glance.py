# Configure the Image service (Glance)

import os
import json
import requests
import hashlib

from ..utils.core.commands import run_command, os_run, os_run_output
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option
from ..utils.core.system_utils import nc_wait
from ..utils.core import colors

glance_conf= "/etc/glance/glance-api.conf"

cirros_image_url = "http://download.cirros-cloud.net/0.6.3/cirros-0.6.3-x86_64-disk.img"
checksums_url = "http://download.cirros-cloud.net/0.6.3/SHA256SUMS"

def install_pkgs():

    packages = ["glance-api"]

    if not apt_install(packages, ux_text=f"Installing Glance package..."): return False

    return True

def conf_glance(config):

    print()
      
    db_password = get(config, "passwords.DATABASE_PASSWORD")
    service_password = get(config, "passwords.SERVICE_PASSWORD")

    os_region_name = get(config, "openstack.REGION_NAME")

    ip_address = get(config, "network.HOST_IP")
      
    set_conf_option(glance_conf, "database", "connection", f"mysql+pymysql://glance:{db_password}@{ip_address}/glance")

    set_conf_option(glance_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000")
    set_conf_option(glance_conf, "keystone_authtoken", "region_name", os_region_name)
    set_conf_option(glance_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(glance_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(glance_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(glance_conf, "keystone_authtoken", "project_domain_name", "Default")
    set_conf_option(glance_conf, "keystone_authtoken", "user_domain_name", "Default")
    set_conf_option(glance_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(glance_conf, "keystone_authtoken", "username", "glance")
    set_conf_option(glance_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(glance_conf, "paste_deploy", "flavor", "keystone")

    set_conf_option(glance_conf, "glance_store", "stores", "file,http")
    set_conf_option(glance_conf, "glance_store", "default_store", "file")
    set_conf_option(glance_conf, "glance_store", "filesystem_store_datadir", "/var/lib/glance/images/")

    db_migration_cmd = [
    "sudo", "-u", "glance",
    "env",
    "PATH=/usr/bin:/usr/local/bin",
    "glance-manage", "db_sync"
]
    if not run_command(db_migration_cmd, "Running Glance DB Migrations...") : return False

    return True

def finalize(config):

    print()

    ip_address = get(config, "network.HOST_IP")

    if not run_command(["systemctl", "restart", "glance-api"], "Restarting Glance service...") : return False

    if not nc_wait(ip_address, 9292) : return False

    return True

def upload_cirros_image(env):

    image_name = "cirros"
    filename = cirros_image_url.split("/")[-1]
    image_file_path = f"/tmp/{filename}"

    images_list_json = os_run_output(
        ["openstack", "image", "list", "-f", "json"],
        env=env
    )
    images_list = json.loads(images_list_json)

    cirros_image_exists = any(
        image.get("Name") == image_name for image in images_list
    )

    if cirros_image_exists:
        return True

    print()

    if not run_command(
        ["wget", "-O", image_file_path, cirros_image_url],
        "Downloading Cirros image...",
        False, None, 5, 5
    ):
        return False

    if not os.path.exists(image_file_path) or os.path.getsize(image_file_path) == 0:
        print(f"{colors.RED}ERROR: Invalid Cirros image download (missing or empty file){colors.RESET}")
        return False

    sha256 = hashlib.sha256()

    with open(image_file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    calculated_hash = sha256.hexdigest()

    checksums_text = requests.get(checksums_url).text
    official_hash = None

    for line in checksums_text.splitlines():
        if filename in line:
            official_hash = line.split()[0]
            break

    if official_hash is None:
        print(f"{colors.RED}ERROR: Unable to retrieve official SHA256 checksum{colors.RESET}")
        return False

    # Compare hashes
    if calculated_hash != official_hash:
        print(
            f"{colors.RED}ERROR: SHA256 checksum mismatch!\n"
            f"Expected: {official_hash}\n"
            f"Got:      {calculated_hash}\n"
            f"The downloaded image may be corrupted or tampered with.{colors.RESET}"
        )
        return False

    if not os_run([
        "openstack", "image", "create",
        image_name,
        "--file", image_file_path,
        "--disk-format", "qcow2",
        "--container-format", "bare",
        "--public"
    ], "Adding Cirros image...", env=env):
        return False

    os.remove(image_file_path)

    return True

def run_setup_glance(config, env):
     
    if not install_pkgs(): return False 
    if not conf_glance(config): return False 
    if not finalize(config): return False 
    if not upload_cirros_image(env): return False

    print(f"\n{colors.GREEN}Glance configured successfully!{colors.RESET}\n")

    return True