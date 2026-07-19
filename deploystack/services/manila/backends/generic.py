# Configure the Generic Backend (Share Node)

import os
import json

from ....utils.core.commands import run_command, os_run, os_run_output
from ....utils.apt.apt import apt_install
from ....utils.config.parser import get
from ....utils.config.setter import set_conf_option
from ....utils.config.helpers import parse_bool

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

    backend_name = get(config, "manila.generic.BACKEND_NAME")

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    os_region_name = get(config, "openstack.REGION_NAME")

    generic_service_instance_flavor = get(config, "manila.generic.SERVICE_INSTANCE_FLAVOR")
    generic_interface_driver = get(config, "manila.generic.INTERFACE_DRIVER")

    generic_service_image_name = get(config, "manila.generic.SERVICE_IMAGE_NAME")

    generic_driver_handles_share_servers = parse_bool(get(config, "manila.generic.DRIVER_HANDLES_SHARE_SERVERS", False))
    generic_share_server_to_tenant_network = parse_bool(get(config, "manila.generic.CONNECT_SHARE_SERVER_TO_TENANT_NETWORK", False))

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

def finalize():

    print()

    if not run_command(["systemctl", "restart", "manila-share"], "Restarting Manila services..."):
        return False

    return True

def finalize_generic_backend(config, env):

    manila_temp_image_path = "/tmp/manila-service-image.qcow2"
    manila_image_url = "https://tarballs.opendev.org/openstack/manila-image-elements/images/manila-service-image-master.qcow2"

    service_network_name = get(config, "manila.SERVICE_NETWORK_NAME")

    generic_service_image_name = get(config, "manila.generic.SERVICE_IMAGE_NAME")

    generic_service_instance_flavor = get(config, "manila.generic.SERVICE_INSTANCE_FLAVOR")

    networks_list = json.loads(os_run_output(["openstack", "network", "list", "-f", "json"], env=env))
    subnets_list = json.loads(os_run_output(["openstack", "subnet", "list", "-f", "json"], env=env))

    share_type_list = json.loads(os_run_output(["openstack", "share", "type", "list", "-f", "json"], env=env))
    flavors_list = json.loads(os_run_output(["openstack", "flavor", "list", "-f", "json"], env=env))

    shares_list = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env))

    internal_network_id: str = ""
    internal_subnet_id: str = ""

    default_share_exists = any(share.get("Name") == "default_share_type" for share in share_type_list)

    if not default_share_exists:

        print()

        if not os_run(["openstack", "share", "type", "create", "default_share_type", "True"], "Creating default share type...", env=env):
            return False
        
        images_list = json.loads(os_run_output(["openstack", "image", "list", "-f", "json"], env=env))

    manila_service_image_exists = any(image.get("Name") == generic_service_image_name for image in images_list)

    if not manila_service_image_exists:
        print()

        if not os.path.exists(manila_temp_image_path):
            if not run_command([
                "wget",
                "--tries=3",
                "--timeout=30",
                "--read-timeout=60",
                "-O", manila_temp_image_path,
                manila_image_url
            ], "Downloading Manila service image... (this may take a while)"):
                return False
        
        if not os_run(["openstack", "image", "create", generic_service_image_name, "--file", manila_temp_image_path, "--disk-format", "qcow2", "--container-format", "bare", "--public"], "Uploading manila image to Glance...", env=env):
            return False     
    
    manila_service_flavor_exists = any(flavor.get("Name") == generic_service_instance_flavor for flavor in flavors_list)

    if not manila_service_flavor_exists:
        print()

        if not os_run(["openstack", "flavor", "create", generic_service_instance_flavor, "--ram", "1024", "--disk", "10", "--vcpus", "1"], "Creating Manila service flavor...", env=env):
            return False
    
    share_networks_list = json.loads(os_run_output(["openstack", "share", "network", "list", "-f", "json"], env=env))

    tenant_share_network_exists = any(network.get("Name") == service_network_name for network in share_networks_list)
    
    if not tenant_share_network_exists:
        print()

        for network in networks_list:
                if network["Name"] == "internal":
                    internal_network_id = network["ID"]

        for subnet in subnets_list:
            if subnet["Name"] == "internal_subnet":
                    internal_subnet_id = subnet["ID"]

        if not os_run(["openstack", "share", "network", "create", "--name", service_network_name, "--neutron-net-id", internal_network_id, "--neutron-subnet-id", internal_subnet_id], "Creating tenant share network...", env=env):
            return False
        
    default_demo_share_exists = any(share.get("Name") == "tenant-share" for share in shares_list)

    if not default_demo_share_exists:
        print()

        if not os_run(["openstack", "share", "create", "NFS", "1", "--name", "tenant-share", "--share-network", service_network_name], "Creating default tenant share...", env=env):
            return False
        
    return True

def run_setup_generic_backend(config, env):

    if not install_pkgs():
        return False
    
    conf_generic_backend(config)

    if not finalize():
        return False
    
    if not finalize_generic_backend(config, env):
        return False
    
    return True

    

    
