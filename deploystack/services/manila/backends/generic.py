# Configure the Generic Backend (Share Node)

import os
import json
import time

from ....utils.core.commands import run_command, os_run, os_run_output
from ....utils.apt.apt import apt_install
from ....utils.config.parser import get
from ....utils.config.setter import set_conf_option
from ....utils.config.helpers import parse_bool

from .helpers import wait_manila_backend, wait_share_available

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

    if not apt_install(["manila-share"], "Installing Manila Share package..."):
        return False

    return True 

def conf_generic_backend(config):

    protocols = get(config, "manila.SHARE_PROTOCOLS", default=["NFS"])
    ip_address = get(config, "network.HOST_IP")

    backend_name = get(config, "manila.backends.generic.BACKEND_NAME")
    service_password = get(config, "passwords.SERVICE_PASSWORD")
    os_region_name = get(config, "openstack.REGION_NAME")

    generic_service_instance_flavor = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR")
    generic_interface_driver = get(config, "manila.backends.generic.INTERFACE_DRIVER")
    generic_service_image_name = get(config, "manila.backends.generic.SERVICE_IMAGE_NAME")

    generic_driver_handles_share_servers = parse_bool(get(config, "manila.backends.generic.DRIVER_HANDLES_SHARE_SERVERS", True))
    generic_share_server_to_tenant_network = parse_bool(get(config, "manila.backends.generic.CONNECT_SHARE_SERVER_TO_TENANT_NETWORK", False))

    enabled_share_protocols = ",".join(protocols)

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
    set_conf_option(manila_conf, "generic", "service_instance_flavor", generic_service_instance_flavor)
    set_conf_option(manila_conf, "generic", "service_image_name", generic_service_image_name)
    set_conf_option(manila_conf, "generic", "service_instance_user", "manila")
    set_conf_option(manila_conf, "generic", "service_instance_password", "manila")
    set_conf_option(manila_conf, "generic", "interface_driver", generic_interface_driver)
    set_conf_option(manila_conf, "generic", "connect_security_service_method", "ssh")
    set_conf_option(manila_conf, "generic", "service_instance_launch_timeout", "300")

    return True


def finalize(env):

    print()

    if not run_command(["systemctl", "restart", "manila-share"], "Restarting Manila services..."):
        return False

    if not wait_manila_backend(env=env):
        return False

    return True


def finalize_generic_backend(config, env):

    manila_temp_image_path = "/tmp/manila-service-image.qcow2"
    manila_image_url = "https://tarballs.opendev.org/openstack/manila-image-elements/images/manila-service-image-master.qcow2"

    service_network_name = get(config, "manila.SERVICE_NETWORK_NAME")
    generic_service_image_name = get(config, "manila.backends.generic.SERVICE_IMAGE_NAME")
    generic_service_instance_flavor_name = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR_NAME")
    default_share_type_name = get(config, "manila.DEFAULT_SHARE_TYPE_NAME") or "default_share_type"

    generic_service_instance_flavor_id = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.ID")
    generic_service_instance_flavor_ram = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.RAM")
    generic_service_instance_flavor_vcpus = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.VCPUS")
    generic_service_instance_flavor_disk = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.DISK")

    shares = get(config, "manila.shares") or []

    networks_list = json.loads(os_run_output(["openstack", "network", "list", "-f", "json"], env=env) or "[]")
    subnets_list = json.loads(os_run_output(["openstack", "subnet", "list", "-f", "json"], env=env) or "[]")
    share_type_list = json.loads(os_run_output(["openstack", "share", "type", "list", "-f", "json"], env=env) or "[]")
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

    # --- Share type ---
    default_share_type_exists = any(
        share_type.get("Name") == default_share_type_name
        for share_type in share_type_list
    )

    if not default_share_type_exists:
        print()
        if not os_run(
            ["openstack", "share", "type", "create", default_share_type_name, "True"],
            "Creating default share type...",
            env=env
        ):
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
            ], "Downloading Manila service image... (this may take a while)"):
                return False

        if not os_run([
            "openstack", "image", "create", generic_service_image_name,
            "--file", manila_temp_image_path,
            "--disk-format", "qcow2",
            "--container-format", "bare",
            "--public"
        ], "Uploading Manila image to Glance...", env=env):
            return False

    # --- Flavor ---
    manila_service_flavor_exists = any(
        flavor.get("Name") == generic_service_instance_flavor_name
        for flavor in flavors_list
    )

    if not manila_service_flavor_exists:
        print()
        if not os_run([
            "openstack", "flavor", "create",
            generic_service_instance_flavor_name,
            "--id", generic_service_instance_flavor_id,
            "--ram", str(generic_service_instance_flavor_ram),
            "--disk", str(generic_service_instance_flavor_disk),
            "--vcpus", str(generic_service_instance_flavor_vcpus)
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
            "--neutron-net-id", internal_network_id,
            "--neutron-subnet-id", internal_subnet_id
        ], "Creating tenant share network...", env=env):
            return False

    # --- Shares ---
    share_list = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env) or "[]")

    for share in shares:
        share_name = share["name"]
        share_type = share.get("share_type", default_share_type_name)
        share_protocol = share["share_protocol"]
        share_size = share["share_size"]

        existing_share = next(
            (item for item in share_list if item.get("Name", item.get("name")) == share_name),
            None
        )

        if existing_share:
            print(f"{colors.YELLOW}{share_name} already exists, checking status...{colors.RESET}")
            share_id = existing_share.get("ID", existing_share.get("id"))
        else:
            if not os_run([
                "openstack", "share", "create",
                "--name", share_name,
                "--share-type", share_type,
                share_protocol, str(share_size)
            ], f"Creating share '{share_name}'...", env=env):
                return False

            share_info = wait_share_available(share_name, env)
            if not share_info:
                return False

            share_id = share_info.get("id")

        if not share_id:
            print(f"\n{colors.RED}ERROR: unable to retrieve {share_name} id{colors.RESET}")
            return False

        export_path = None
        for _ in range(10):
            share_info = json.loads(os_run_output(["openstack", "share", "show", share_id, "-f", "json"], env=env) or "{}")
            export_locations = share_info.get("export_locations", "")

            if isinstance(export_locations, str):
                for line in export_locations.splitlines():
                    if line.strip().startswith("path ="):
                        export_path = line.split("=", 1)[1].strip()
                        break
            elif isinstance(export_locations, list):
                first = export_locations[0]
                export_path = first.get("path") if isinstance(first, dict) else first

            if export_path:
                break
            time.sleep(3)

        if not export_path:
            print(f"\n{colors.RED}ERROR: {share_name} has no export location available{colors.RESET}")
            return False

        # Access rules
        print()
        access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")

        for rule in share.get("access_rules", []):
            rule_type = rule["type"]
            rule_access = rule["access"]
            rule_level = rule["level"]

            rule_exists = any(
                access.get("access_type", access.get("Access Type")) == rule_type
                and access.get("access_to", access.get("Access To")) == rule_access
                for access in access_list
            )

            if rule_exists:
                print(f"{colors.YELLOW}Access rule {rule_access} already exists, skipping.{colors.RESET}")
                continue

            if not os_run([
                "openstack", "share", "access", "create",
                "--access-level", rule_level,
                share_id, rule_type, rule_access
            ], f"Adding access rule {rule_access} to '{share_name}'...", env=env):
                return False

            for _ in range(10):
                access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")
                if any(
                    access.get("access_type", access.get("Access Type")) == rule_type
                    and access.get("access_to", access.get("Access To")) == rule_access
                    for access in access_list
                ):
                    break
                time.sleep(2)
            else:
                print(f"\n{colors.RED}ERROR: access rule {rule_access} not created{colors.RESET}")
                return False

    return True


def run_setup_generic_backend(config, env):

    if not install_pkgs(): return False

    conf_generic_backend(config)

    if not finalize(env): return False

    if not finalize_generic_backend(config, env): return False

    return True