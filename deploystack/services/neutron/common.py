# Configure the Networking service (Neutron) (Controller Node)

import os

from ...utils.core.commands import run_command
from ...utils.apt.apt import apt_install, apt_update
from ...utils.config.parser import get
from ...utils.config.setter import set_conf_option, set_service_option
from ...utils.core.system_utils import service_exists, is_debian, is_ubuntu_release
from ...utils.core import colors

neutron_conf = "/etc/neutron/neutron.conf"
conf_ml2 = "/etc/neutron/plugins/ml2/ml2_conf.ini"
conf_metadata_agent = "/etc/neutron/metadata_agent.ini"
conf_nova = "/etc/nova/nova.conf"

apache2_systemd_unit = "/usr/lib/systemd/system/apache2.service"

def install_pkgs():
    
    if not apt_update() : return False

    neutron_packages = [
        "neutron-server",
        "neutron-plugin-ml2", 
    ]

    if not apt_install(neutron_packages, ux_text="Installing Neutron packages..."):
        return False

    return True

def conf_neutron(config):

    link = "/etc/neutron/plugin.ini"

    database_password = get(config, "passwords.DATABASE_PASSWORD")
    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    driver = config.get("neutron", {}).get("DRIVER", "ovs").lower()

    os_region_name = get(config, "openstack.REGION_NAME")

    service_plugins = "ovn-router" if driver == "ovn" else "router"

    ip_address = get(config, "network.HOST_IP")

    set_conf_option(neutron_conf, "database", "connection", f"mysql+pymysql://neutron:{database_password}@{ip_address}/neutron")

    set_conf_option(neutron_conf, "DEFAULT", "core_plugin", "ml2")
    set_conf_option(neutron_conf, "DEFAULT", "transport_url", f"rabbit://openstack:{rabbitmq_password}@{ip_address}")
    set_conf_option(neutron_conf, "DEFAULT", "auth_strategy", "keystone")
    set_conf_option(neutron_conf, "DEFAULT", "service_plugins", service_plugins)
    set_conf_option(neutron_conf, "DEFAULT", "notify_nova_on_port_status_changes", "true")
    set_conf_option(neutron_conf, "DEFAULT", "notify_nova_on_port_data_changes", "true")

    set_conf_option(neutron_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000")
    set_conf_option(neutron_conf, "keystone_authtoken", "region_name", os_region_name)
    set_conf_option(neutron_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(neutron_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(neutron_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(neutron_conf, "keystone_authtoken", "project_domain_name", "default")
    set_conf_option(neutron_conf, "keystone_authtoken", "user_domain_name", "default")
    set_conf_option(neutron_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(neutron_conf, "keystone_authtoken", "username", "neutron")
    set_conf_option(neutron_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(neutron_conf, "nova", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(neutron_conf, "nova", "auth_type", "password")
    set_conf_option(neutron_conf, "nova", "project_domain_name", "default")
    set_conf_option(neutron_conf, "nova", "user_domain_name", "default")
    set_conf_option(neutron_conf, "nova", "region_name", os_region_name)
    set_conf_option(neutron_conf, "nova", "project_name", "service")
    set_conf_option(neutron_conf, "nova", "username", "nova")
    set_conf_option(neutron_conf, "nova", "password", service_password)

    set_conf_option(neutron_conf, "oslo_concurrency", "lock_path", "/var/lib/neutron/tmp")

    set_conf_option(conf_metadata_agent, "DEFAULT", "nova_metadata_host", ip_address)
    set_conf_option(conf_metadata_agent, "DEFAULT", "metadata_proxy_shared_secret", service_password)

    set_conf_option(conf_nova, "neutron", "auth_url", f"http://{ip_address}:5000")
    set_conf_option(conf_nova, "neutron", "auth_type", "password")
    set_conf_option(conf_nova, "neutron", "project_domain_name", "default")
    set_conf_option(conf_nova, "neutron", "user_domain_name", "default")
    set_conf_option(conf_nova, "neutron", "region_name", os_region_name)
    set_conf_option(conf_nova, "neutron", "project_name", "service")
    set_conf_option(conf_nova, "neutron", "username", "neutron")
    set_conf_option(conf_nova, "neutron", "password", service_password)
    set_conf_option(conf_nova, "neutron", "service_metadata_proxy", "true")
    set_conf_option(conf_nova, "neutron", "metadata_proxy_shared_secret", service_password)

    if os.path.islink(link):
        os.remove(link)
    if not os.path.exists(link):
        os.symlink(conf_ml2, link)

    print()

    neutron_db_migration_cmd = [
    "sudo", "-u", "neutron",
    "neutron-db-manage", "--config-file", neutron_conf,  "--config-file", conf_ml2, "upgrade", "head"]
    
    if not run_command(neutron_db_migration_cmd, "Running Neutron DB Migrations...") : return False

    return True

def finalize():

    print()

    if not is_debian() and is_ubuntu_release("26.04"):
        set_service_option(apache2_systemd_unit, "Service", "ProtectProc", "default")
        set_service_option(apache2_systemd_unit, "Service", "ProcSubset", "all")

        if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

    if service_exists("nova-api.service"):
        if not run_command(["systemctl", "restart", "nova-api"], "Restarting Nova API service...", False, None, 3, 5): return False

    if service_exists("neutron-server.service"):
        if not run_command(["systemctl", "restart", "neutron-server", "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False
    elif service_exists("neutron-api.service") and is_debian():
        if not run_command(["systemctl", "restart", "neutron-api", "neutron-rpc-server",  "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False
    else:
        if not run_command(["systemctl", "restart", "neutron-periodic-workers", "apache2", "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False

    return True

def run_setup_neutron_common(config, driver_fn, env):
    
    if not install_pkgs(): return False
    if not conf_neutron(config): return False
    if not finalize(): return False
    if not driver_fn(config, env): return False

    print(f"\n{colors.GREEN}Neutron configured successfully!{colors.RESET}\n")
    return True