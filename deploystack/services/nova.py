# Configure the Compute service (Nova)

import os
import stat

from ..utils.core.commands import run_command, run_command_sync, os_run
from ..utils.core.system_utils import service_exists
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option, set_service_option
from ..utils.core.system_utils import nc_wait, is_debian
from ..utils.core import colors

nova_conf = "/etc/nova/nova.conf"
nova_novncproxy_service = "/lib/systemd/system/nova-novncproxy.service"

def install_pkgs():

    packages = ["nova-api", "nova-conductor", "nova-novncproxy", "nova-scheduler"]

    if not apt_install(packages, ux_text=f"Installing Nova packages...") : return False

    return True

def conf_nova(config):
      
    print()

    install_cinder = get(config, "optional_services.INSTALL_CINDER", "no") == "yes"

    database_password = get(config, "passwords.DATABASE_PASSWORD")
    rabbitmq_password = get(config, "passwords.RABBITMQ_PASSWORD")

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    os_region_name = get(config, "openstack.REGION_NAME")

    ip_address = get(config, "network.HOST_IP")

    set_conf_option(nova_conf, "api_database", "connection", f"mysql+pymysql://nova:{database_password}@{ip_address}/nova_api")
    set_conf_option(nova_conf, "database", "connection", f"mysql+pymysql://nova:{database_password}@{ip_address}/nova")

    set_conf_option(nova_conf, "DEFAULT", "transport_url", f"rabbit://openstack:{rabbitmq_password}@{ip_address}:5672/")
    set_conf_option(nova_conf, "DEFAULT", "force_config_drive", "true")

    set_conf_option(nova_conf, "api", "auth_strategy", "keystone")

    set_conf_option(nova_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000/")
    set_conf_option(nova_conf, "keystone_authtoken", "region_name", os_region_name)
    set_conf_option(nova_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000/")
    set_conf_option(nova_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(nova_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(nova_conf, "keystone_authtoken", "project_domain_name", "Default")
    set_conf_option(nova_conf, "keystone_authtoken", "user_domain_name", "Default")
    set_conf_option(nova_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(nova_conf, "keystone_authtoken", "username", "nova")
    set_conf_option(nova_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(nova_conf, "vnc", "enabled", "true")
    set_conf_option(nova_conf, "vnc", "server_listen", ip_address)
    set_conf_option(nova_conf, "vnc", "server_proxyclient_address", ip_address)
    set_conf_option(nova_conf, "vnc", "novncproxy_base_url", f"http://{ip_address}:6080/vnc_auto.html")

    set_conf_option(nova_conf, "glance", "api_servers", f"http://{ip_address}:9292")

    if install_cinder:
        set_conf_option(nova_conf, "cinder", "os_region_name", os_region_name)
        set_conf_option(nova_conf, "cinder", "auth_url", f"http://{ip_address}:5000/v3")
        set_conf_option(nova_conf, "cinder", "auth_type", "password")
        set_conf_option(nova_conf, "cinder", "project_domain_name", "Default")
        set_conf_option(nova_conf, "cinder", "user_domain_name", "Default")
        set_conf_option(nova_conf, "cinder", "project_name", "service")
        set_conf_option(nova_conf, "cinder", "username", "cinder")
        set_conf_option(nova_conf, "cinder", "password", service_password)

    set_conf_option(nova_conf, "oslo_concurrency", "lock_path", "/var/lib/nova/tmp")

    set_conf_option(nova_conf, "placement", "region_name", os_region_name)
    set_conf_option(nova_conf, "placement", "project_domain_name", "Default")
    set_conf_option(nova_conf, "placement", "project_name", "service")
    set_conf_option(nova_conf, "placement", "auth_type", "password")
    set_conf_option(nova_conf, "placement", "user_domain_name", "Default")
    set_conf_option(nova_conf, "placement", "auth_url", f"http://{ip_address}:5000/v3")
    set_conf_option(nova_conf, "placement", "username", "placement")
    set_conf_option(nova_conf, "placement", "password", service_password)

    api_db_migration_cmd = [
    "sudo", "-u", "nova",
    "nova-manage", "api_db", "sync"
]
    
    register_cell0_migration_cmd = [
    "sudo", "-u", "nova",
    "nova-manage", "cell_v2", "map_cell0",
]
    
    create_cell1_migration_cmd = [
    "sudo", "-u", "nova",
    "nova-manage", "cell_v2", "create_cell",
    "--name=cell1", "--verbose"
]
    db_migration_cmd = [
    "sudo", "-u", "nova",
    "nova-manage", "db", "sync"
]
     
    if not run_command(api_db_migration_cmd, "Running Nova API DB Migrations...") : return False

    print()
    
    if not run_command(register_cell0_migration_cmd, "Registering Nova cell0 in the database...") : return False

    print()
    
    if not run_command(create_cell1_migration_cmd, "Creating initial Nova cell1 for VM scheduling...", ignore_exit_codes=[2]) : return False
    
    print()
    
    if not run_command(db_migration_cmd, "Running Nova DB Migrations...") : return False
    
    return True

def finalize(config):

    ip_address = get(config, "network.HOST_IP")

    services_to_restart = ["nova-scheduler", "nova-conductor", "nova-novncproxy"]

    if is_debian() and service_exists("nova-serialproxy.service") and service_exists("nova-spicehtml5proxy.service"):
             
        print()

        set_service_option(nova_novncproxy_service, "Service", "ExecStart", "/usr/bin/nova-novncproxy --config-file=/etc/nova/nova.conf")

        run_command_sync(["systemctl", "disable", "nova-spicehtml5proxy", "nova-serialproxy"])
        run_command_sync(["systemctl", "enable", "nova-novncproxy"])

        if not run_command(["systemctl", "daemon-reload"], "Reloading systemd daemon..."): return False

        print()
    else:
        print()

    if service_exists("nova-api.service"):
        services_to_restart.insert(0, "nova-api")

    if not run_command(["systemctl", "restart"] + services_to_restart, "Restarting Nova services...", False, None, 3, 5): return False
    
    if not nc_wait(ip_address, 8774) : return False

    return True

def add_default_keypair(env):
    print()

    key_name = "default"
    key_file = f"/root/{key_name}.pem"

    check_cmd = ["openstack", "keypair", "show", key_name]
    exists = run_command_sync(check_cmd, env)

    if exists:
        print(f"{colors.YELLOW}Keypair '{key_name}' already exists, skipping creation.{colors.RESET}")
        return True

    create_cmd = ["openstack", "keypair", "create", key_name, "--private-key", key_file]
    if not os_run(create_cmd, "Creating default keypair...", env) : return False

    os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
    os.chown(key_file, os.getuid(), os.getgid())

    print(f"{colors.YELLOW}Keypair '{key_name}' created and saved to {key_file}{colors.RESET}")
    return True

def run_setup_nova(config, env):
     
    if not install_pkgs(): return False  
    if not conf_nova(config): return False 
    if not finalize(config): return False
    if not add_default_keypair(env): return False
    
    print(f"\n{colors.GREEN}Nova configured successfully!{colors.RESET}\n")
    return True
    