# Configure the Generic Backend (Share Node)

import os
import json
import shutil

from ....utils.core.commands import run_command, os_run, os_run_output
from ....utils.apt.apt import apt_install
from ....utils.config.parser import get
from ....utils.config.setter import set_conf_option
from ....utils.config.helpers import parse_bool
from ....utils.core import colors

from ....utils.core.system_utils import build_openstack_env_from_file

from ...nova import nova_conf
from ...neutron.ovs import conf_openvswitch

from .utils import wait_manila_backend
from .utils.shares import create_shares, create_share_types

from .protocols.nfs import run_setup_nfs

manila_conf = "/etc/manila/manila.conf"

manila_temp_image_file = "/tmp/manila-service-image.qcow2"
manila_image_url = "https://tarballs.opendev.org/openstack/manila-image-elements/images/manila-service-image-master.qcow2"

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

    if not apt_install(["manila-share", "libguestfs-tools"], "Installing Manila Share and libguestfs tools..."): return False

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

    neutron_driver = config.get("neutron", {}).get("DRIVER", "ovs").lower()

    generic_share_server_to_tenant_network = parse_bool(get(config, "manila.backends.generic.CONNECT_SHARE_SERVER_TO_TENANT_NETWORK", False))

    enabled_share_protocols = ",".join(protocols)

    share_helpers = get(config, "manila.SHARE_HELPERS") or []

    service_image_authentication_method = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.AUTH_METHOD", "password")

    service_instance_user = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.SERVICE_INSTANCE_USER", "manila")
    service_instance_password = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.SERVICE_INSTANCE_PASSWORD", "manila")

    if "NFS" in protocols:
        if not run_setup_nfs(): return False

    helpers = [
        f"{helper_type}={config.get('name')}"
        for helper in share_helpers
        for helper_type, config in helper.items()
    ]

    set_conf_option(manila_conf, "DEFAULT", "share_helpers", ",".join(helpers))

    set_conf_option(manila_conf, "DEFAULT", "enabled_share_backends", "generic")
    set_conf_option(manila_conf, "DEFAULT", "enabled_share_protocols", enabled_share_protocols)

    _set_service_auth(manila_conf, "neutron", "neutron", ip_address, os_region_name, service_password)
    _set_service_auth(manila_conf, "nova", "nova", ip_address, os_region_name, service_password)
    _set_service_auth(manila_conf, "glance", "glance", ip_address, os_region_name, service_password)
    _set_service_auth(manila_conf, "cinder", "cinder", ip_address, os_region_name, service_password)

    set_conf_option(manila_conf, "generic", "share_backend_name", backend_name)
    set_conf_option(manila_conf, "generic", "share_driver", "manila.share.drivers.generic.GenericShareDriver")
    set_conf_option(manila_conf, "generic", "driver_handles_share_servers", "True")
    set_conf_option(manila_conf, "generic", "connect_share_server_to_tenant_network", str(generic_share_server_to_tenant_network))
    set_conf_option(manila_conf, "generic", "service_instance_flavor_id", str(generic_service_instance_flavor_id))
    set_conf_option(manila_conf, "generic", "service_image_name", generic_service_image_name)

    if service_image_authentication_method == "password":

        set_conf_option(manila_conf, "generic", "service_instance_user", service_instance_user)
        set_conf_option(manila_conf, "generic", "service_instance_password", service_instance_password)

    elif service_image_authentication_method == "ssh_key":

        service_instance_private_key = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.SERVICE_INSTANCE_PRIVATE_KEY", "/etc/manila/ssh/id_manila")
        service_instance_public_key = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.SERVICE_INSTANCE_PUBLIC_KEY", "/etc/manila/ssh/id_manila.pub")

        set_conf_option(manila_conf, "generic", "service_instance_user", service_instance_user)
        set_conf_option(manila_conf, "generic", "service_instance_password", service_instance_password)

        set_conf_option(manila_conf, "generic", "path_to_private_key", service_instance_private_key)
        set_conf_option(manila_conf, "generic", "path_to_public_key", service_instance_public_key)

    set_conf_option(manila_conf, "generic", "interface_driver", generic_interface_driver)
    set_conf_option(manila_conf, "generic", "connect_security_service_method", "ssh")
    set_conf_option(manila_conf, "generic", "service_instance_launch_timeout", "600")
    set_conf_option(manila_conf, "generic", "max_time_to_build_instance", "600")

    if neutron_driver == "ovs":
        set_conf_option(conf_openvswitch, "agent", "tunnel_types", "vxlan")

    set_conf_option(nova_conf, "DEFAULT", "resume_guests_state_on_host_boot", "true")

    return True

def finalize(env):

    print()

    if not run_command(["systemctl", "restart", "manila-api", "manila-scheduler", "manila-share"], "Restarting Manila Share services...", False, None, 3, 5):
        return False

    print()

    if not wait_manila_backend(env=env):
        return False

    return True

def create_shares_networks(config, env):

    line_printed = False

    service_networks = get(config, "manila.backends.generic.service_networks") or []

    networks_list = json.loads(os_run_output(["openstack", "network", "list", "-f", "json"], env=env) or "[]")

    demo_env = build_openstack_env_from_file("/root/demo-openrc.sh")

    admin_share_networks_list = json.loads(os_run_output(["openstack", "share", "network", "list", "-f", "json"], env=env) or "[]")
    demo_share_networks_list = json.loads(os_run_output(["openstack", "share", "network", "list", "-f", "json"], env=demo_env) or "[]")

    project_commands = {
        "admin": [],
        "demo": [],
    }

    project_envs = {
        "admin": env,
        "demo": demo_env,
    }

    for service_net in service_networks:

        network_name = service_net["name"]
        neutron_network = service_net["neutron_network"]

        neutron_network_id = ""
    
        for network in networks_list:
            if (network.get("Name") or network.get("name")) == neutron_network:
                neutron_network_id = network.get("ID") or network.get("id")
                break
        if not neutron_network_id:
            print(f"{colors.RED}Neutron network '{neutron_network}' not found.{colors.RESET}")
            return False

        neutron_network_subnets_list = json.loads(os_run_output(["openstack", "subnet", "list", "--network", neutron_network_id, "-f", "json"], env=env) or "[]")

        neutron_subnet_id = ""

        for subnet in neutron_network_subnets_list:
            neutron_subnet_id = subnet.get("ID") or subnet.get("id")
            break

        if not neutron_subnet_id:
            print(f"{colors.RED}No subnet found for Neutron network '{neutron_network}'.{colors.RESET}")
            return False

        admin_share_network_exists = any(
            (sn.get("Name") or sn.get("name")) == network_name
            for sn in admin_share_networks_list
        )

        demo_share_network_exists = any(
            (sn.get("Name") or sn.get("name")) == network_name
            for sn in demo_share_networks_list
        )

        share_network_command = [
            "openstack",
            "share",
            "network",
            "create",
            "--name", network_name,
            "--neutron-net-id", str(neutron_network_id),
            "--neutron-subnet-id", str(neutron_subnet_id),
        ]

        if not admin_share_network_exists:
            project_commands["admin"].append({
                "command": share_network_command.copy(),
                "name": network_name,
            })

        if not demo_share_network_exists:
            project_commands["demo"].append({
                "command": share_network_command.copy(),
                "name": network_name,
            })

    for project, commands in project_commands.items():
        for item in commands:
            if not line_printed:
                line_printed = True
                print()

            if not os_run(
                item["command"],
                f"Creating share network '{item['name']}' for '{project}' project...",
                env=project_envs[project]): return False

    return True
    
def finalize_generic_backend(config, env):

    create_shares_enabled = parse_bool(get(config, "manila.CREATE_SHARES") , False)

    generic_service_image_name = get(config, "manila.backends.generic.SERVICE_IMAGE_NAME")

    default_type_shares = get(config, "manila.share_types") or []

    generic_service_instance_flavor_name = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.NAME")
    generic_service_instance_flavor_id = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.ID")
    generic_service_instance_flavor_ram = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.RAM")
    generic_service_instance_flavor_vcpus = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.VCPUS")
    generic_service_instance_flavor_disk = get(config, "manila.backends.generic.SERVICE_INSTANCE_FLAVOR.DISK")

    service_image_authentication_method = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.AUTH_METHOD", "password")

    images_list = json.loads(os_run_output(["openstack", "image", "list", "-f", "json"], env=env) or "[]")
    flavors_list = json.loads(os_run_output(["openstack", "flavor", "list", "-f", "json"], env=env) or "[]")
    
    if not create_share_types(default_type_shares=default_type_shares, env=env): return False

    manila_service_image_exists = any(image.get("Name") == generic_service_image_name for image in images_list)

    if not manila_service_image_exists:
        print()

        if not os.path.exists(manila_temp_image_file):
            if not run_command(["wget", "--continue", "--progress=dot:giga", "--tries=3", "--timeout=30", "--read-timeout=60","-O", manila_temp_image_file, manila_image_url], "Downloading Manila service image... (this may take a while) ", timeout=3600): return False

        print()

        if not run_command(["virt-customize", "-a", manila_temp_image_file, "--run-command", "systemctl disable fetch-public-ssh-keys.service"], "Preparing Manila service image...", timeout=600) : return False

        if os.path.exists(manila_temp_image_file):
            if not os_run(["openstack", "image", "create", generic_service_image_name, "--file", manila_temp_image_file, "--disk-format", "qcow2", "--container-format", "bare", "--public"], "Uploading Manila image to Glance...", env=env): return False
        
        try:
            os.remove(manila_temp_image_file)
        except FileNotFoundError:
            pass

    if service_image_authentication_method == "ssh_key":

        service_instance_private_key = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.SERVICE_INSTANCE_PRIVATE_KEY", "/etc/manila/ssh/id_manila")
        service_instance_public_key = get(config, "manila.backends.generic.SERVICE_IMAGE_AUTHENTICATION.SERVICE_INSTANCE_PUBLIC_KEY", "/etc/manila/ssh/id_manila.pub")

        key_dir = os.path.dirname(service_instance_private_key)
        
        if not os.path.exists(service_instance_private_key) or not os.path.exists(service_instance_public_key):
            print()

            if not os.path.exists(key_dir):
                os.makedirs(key_dir, mode=0o700, exist_ok=True)

            if not run_command(["ssh-keygen", "-t", "rsa", "-b", "2048", "-N", "", "-f", service_instance_private_key], "Generating Manila SSH Key...") : return False

        try:
            shutil.chown(key_dir, user="manila", group="manila")
            shutil.chown(service_instance_private_key, user="manila", group="manila")
            shutil.chown(service_instance_public_key, user="manila", group="manila")

            os.chmod(key_dir, 0o700)
            os.chmod(service_instance_private_key, 0o600)
            os.chmod(service_instance_public_key, 0o644)
        except Exception as e:
            print(f"{colors.RED}Failed to configure Manila SSH key permissions: {e}{colors.RESET}")
            return False

    manila_service_flavor_exists = any(flavor.get("Name") == generic_service_instance_flavor_name for flavor in flavors_list)

    if not manila_service_flavor_exists:
        print()
        if not os_run(["openstack", "flavor", "create", "--id", str(generic_service_instance_flavor_id), "--ram", str(generic_service_instance_flavor_ram), "--disk", str(generic_service_instance_flavor_disk), "--vcpus", str(generic_service_instance_flavor_vcpus), generic_service_instance_flavor_name], "Creating Manila service flavor...", env=env): return False

    if not create_shares_networks(config, env) : return False

    if create_shares_enabled:
        shares = get(config, "manila.shares") or []

        if not create_shares(shares=shares, env=env, dhss=True): return False

    return True

def run_setup_generic_backend(config, env):

    if not install_pkgs(): return False

    conf_generic_backend(config)

    if not finalize(env): return False

    if not finalize_generic_backend(config, env): return False

    return True