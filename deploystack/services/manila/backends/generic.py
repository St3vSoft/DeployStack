# Configure the Generic Backend (Share Node)

import os
import json

from ....utils.core.commands import run_command, os_run, os_run_output
from ....utils.apt.apt import apt_install
from ....utils.config.parser import get
from ....utils.config.setter import set_conf_option
from ....utils.config.helpers import parse_bool

from .utils import wait_manila_backend
from .utils.shares import create_shares, create_share_types

from .protocols.nfs import run_setup_nfs
from .protocols.samba import run_setup_samba

from ....utils.core.system_utils import is_package_installed

from ....utils.core import colors

manila_conf = "/etc/manila/manila.conf"

def _set_service_auth(conf, section, username, ip_address, region, password):
    set_conf_option(conf, section, "auth_url", f"http://{ip_address}:5000")
    set_conf_option(conf, section, "auth_type", "password")
    set_conf_option(conf, section, "memcached_servers", "127.0.0.1:11211")
    set_conf_option(conf, section, "project_domain_name", "Default")
    set_conf_option(conf, section, "user_domain_name", "Default")
    set_conf_option(conf, section, "region_name", region)
    set_conf_option(conf, section, "project_name", "service")
    set_conf_option(conf, section, "username", username)
    set_conf_option(conf, section, "password", password)

def install_pkgs():

    print()

    if not apt_install(["manila-share"], "Installing Manila Share package..."):
        return False

    return True 

def conf_generic_backend(config):

    protocols = get(config, "manila.SHARE_PROTOCOLS", default=["NFS"])
    ip_address = get(config, "network.HOST_IP")

    backend_name = get(config, "manila.backends.generic.BACKEND_NAME")
    service_password = get(config, "passwords.SERVICE_PASSWORD")
    os_region_name = get(config, "openstack.REGION_NAME")

    generic_service_instance_flavor_id = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.ID")
    generic_interface_driver = get(config, "manila.backends.generic.INTERFACE_DRIVER")
    generic_service_image_name = get(config, "manila.backends.generic.SERVICE_IMAGE_NAME")

    generic_driver_handles_share_servers = parse_bool(get(config, "manila.backends.generic.DRIVER_HANDLES_SHARE_SERVERS", True))
    generic_share_server_to_tenant_network = parse_bool(get(config, "manila.backends.generic.CONNECT_SHARE_SERVER_TO_TENANT_NETWORK", False))

    enabled_share_protocols = ",".join(protocols)

    share_helpers = get(config, "manila.SHARE_HELPERS") or []
    
    helpers = []

    if "NFS" in protocols:
        if not run_setup_nfs(): return False
    
    if "CIFS" in protocols:
        if not run_setup_samba(config): return False

    for helper in share_helpers:
            for helper_type, config in helper.items():
                helper_name = config.get("name")
                helpers.append(f"{helper_type}={helper_name}")

    set_conf_option(manila_conf, "DEFAULT", "share_helpers", f"{helper_type}={helper_name}")

    set_conf_option(manila_conf, "DEFAULT", "enabled_share_backends", "generic")
    set_conf_option(manila_conf, "DEFAULT", "enabled_share_protocols", enabled_share_protocols)

    _set_service_auth(manila_conf, "neutron", "neutron", ip_address, os_region_name, service_password)
    _set_service_auth(manila_conf, "nova", "nova", ip_address, os_region_name, service_password)
    _set_service_auth(manila_conf, "glance", "glance", ip_address, os_region_name, service_password)
    _set_service_auth(manila_conf, "cinder", "cinder", ip_address, os_region_name, service_password)

    set_conf_option(manila_conf, "generic", "share_backend_name", backend_name)
    set_conf_option(manila_conf, "generic", "share_driver", "manila.share.drivers.generic.GenericShareDriver")
    set_conf_option(manila_conf, "generic", "driver_handles_share_servers", str(generic_driver_handles_share_servers))
    set_conf_option(manila_conf, "generic", "connect_share_server_to_tenant_network", str(generic_share_server_to_tenant_network))
    set_conf_option(manila_conf, "generic", "service_instance_flavor_id", str(generic_service_instance_flavor_id))
    set_conf_option(manila_conf, "generic", "service_image_name", generic_service_image_name)
    set_conf_option(manila_conf, "generic", "service_instance_user", "manila")
    set_conf_option(manila_conf, "generic", "service_instance_password", "manila")
    set_conf_option(manila_conf, "generic", "interface_driver", generic_interface_driver)
    set_conf_option(manila_conf, "generic", "connect_security_service_method", "ssh")
    set_conf_option(manila_conf, "generic", "service_instance_launch_timeout", "300")

    return True


def finalize(env):

    print()

    if not run_command(["systemctl", "restart", "manila-api", "manila-scheduler", "manila-share"], "Restarting Manila Share services..."):
        return False

    if not wait_manila_backend(env=env):
        return False

    return True


def finalize_generic_backend(config, env):

    manila_temp_image_path = "/tmp/manila-service-image.qcow2"
    manila_image_url = "https://tarballs.opendev.org/openstack/manila-image-elements/images/manila-service-image-master.qcow2"

    service_network_name = get(config, "manila.backends.generic.SERVICE_NETWORK_NAME")
    generic_service_image_name = get(config, "manila.backends.generic.SERVICE_IMAGE_NAME")
    generic_service_instance_flavor_name = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR_NAME")

    generic_service_instance_flavor_id = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.ID")
    generic_service_instance_flavor_ram = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.RAM")
    generic_service_instance_flavor_vcpus = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.VCPUS")
    generic_service_instance_flavor_disk = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.DISK")

    shares = get(config, "manila.shares") or []
    default_type_shares = get(config, "manila.share_types") or []

    networks_list = json.loads(os_run_output(["openstack", "network", "list", "-f", "json"], env=env) or "[]")
    subnets_list = json.loads(os_run_output(["openstack", "subnet", "list", "-f", "json"], env=env) or "[]")
    images_list = json.loads(os_run_output(["openstack", "image", "list", "-f", "json"], env=env) or "[]")
    flavors_list = json.loads(os_run_output(["openstack", "flavor", "list", "-f", "json"], env=env) or "[]")

    # --- Risolvi network e subnet ---
    internal_network_id = ""
    internal_subnet_id = ""

    for network in networks_list:
        if network["Name"] == "internal":
            internal_network_id = network["ID"]

    for subnet in subnets_list:
        if subnet["Name"] == "internal_subnet":
            internal_subnet_id = subnet["ID"]

    if not internal_network_id:
        print(f"{colors.RED}Error: internal network not found{colors.RESET}")
        return False

    if not internal_subnet_id:
        print(f"{colors.RED}Error: internal subnet not found{colors.RESET}")
        return False

    if not create_share_types(default_type_shares=default_type_shares, env=env):
        return False

    # --- Immagine ---
    manila_service_image_exists = any(
        image.get("Name") == generic_service_image_name
        for image in images_list
    )

    if not manila_service_image_exists:
        print()
        if not os.path.exists(manila_temp_image_path):
            if not run_command([
                "wget", "--tries=3", "--timeout=30", "--read-timeout=60",
                "-O", manila_temp_image_path, manila_image_url
            ], "Downloading Manila service image... (this may take a while) ", timeout=3600):
                return False

        if not os_run([
            "openstack", "image", "create", generic_service_image_name,
            "--file", manila_temp_image_path,
            "--disk-format", "qcow2",
            "--container-format", "bare",
            "--public"
        ], "Uploading Manila image to Glance...", env=env):
            return False
        
        os.remove(manila_temp_image_path)

    # --- Flavor ---
    manila_service_flavor_exists = any(
        flavor.get("Name") == generic_service_instance_flavor_name
        for flavor in flavors_list
    )

    if not manila_service_flavor_exists:
        print()
        if not os_run([
            "openstack", "flavor", "create",
            "--id", str(generic_service_instance_flavor_id),
            "--ram", str(generic_service_instance_flavor_ram),
            "--disk", str(generic_service_instance_flavor_disk),
            "--vcpus", str(generic_service_instance_flavor_vcpus),
            generic_service_instance_flavor_name,
        ], "Creating Manila service flavor...", env=env):
            return False

    # --- Share network ---
    share_networks_list = json.loads(os_run_output(["openstack", "share", "network", "list", "-f", "json"], env=env) or "[]")

    tenant_share_network_exists = any(
        network.get("Name") == service_network_name
        for network in share_networks_list
    )

    if not tenant_share_network_exists:
        print()
        if not os_run([
            "openstack", "share", "network", "create",
            "--name", service_network_name,
            "--neutron-net-id", str(internal_network_id),
            "--neutron-subnet-id", str(internal_subnet_id),
        ], "Creating tenant share network...", env=env):
            return False

    if not create_shares(shares=shares, env=env, dhss=True, service_network_name=service_network_name):
        return False

    return True


def run_setup_generic_backend(config, env):

    if not install_pkgs(): return False

    conf_generic_backend(config)

    if not finalize(env): return False

    if not finalize_generic_backend(config, env): return False

    return True