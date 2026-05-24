# Configure the Identity service (Keystone)

import os

from ..utils.core.commands import run_command, os_run, os_run_output
from ..utils.core.system_utils import service_exists, build_openstack_env
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option
from ..utils.core.system_utils import nc_wait
from ..utils.core import colors

keystone_conf = "/etc/keystone/keystone.conf"

def install_pkgs():

    packages = ["keystone", "apache2"]

    if not apt_install(packages, ux_text=f"Installing Keystone packages...") : return False

    return True

def conf_keystone(config):

    print()
      
    db_password = get(config, "passwords.DATABASE_PASSWORD")
    ip_address = get(config, "network.HOST_IP")

    admin_password = get(config, "passwords.ADMIN_PASSWORD")

    os_region_name = get(config, "openstack.REGION_NAME")

    identity_url = f"http://{ip_address}:5000/v3/"

    set_conf_option(keystone_conf, "database", "connection", f"mysql+pymysql://keystone:{db_password}@{ip_address}/keystone")

    set_conf_option(keystone_conf, "database", "max_pool_size", "20")
    set_conf_option(keystone_conf, "database", "max_overflow", "100")
    set_conf_option(keystone_conf, "database", "pool_timeout", "60")

    set_conf_option(keystone_conf, "token", "provider", "fernet")

    db_migration_cmd = [
        "sudo", "-u", "keystone",
        "env",
        "PATH=/usr/bin:/usr/local/bin",
        "keystone-manage", "db_sync"
    ]

    if not run_command(db_migration_cmd, "Running Keystone DB Migrations...") : return False

    print()

    fernet_credentials_setup_cmds = [
        (["sudo", "-u", "keystone", "keystone-manage", "fernet_setup", "--keystone-user", "keystone", "--keystone-group", "keystone"],
         "Setting up Keystone Fernet Keys..."),
        (["sudo", "-u", "keystone", "keystone-manage", "credential_setup", "--keystone-user", "keystone", "--keystone-group", "keystone"],
         "Setting up Keystone Credentials Database...")
    ]

    for cmd, message in fernet_credentials_setup_cmds:
        success = run_command(cmd, message)
        if not success:
            return False
    
    bootstrap_cmd = [
        "sudo", "-u", "keystone",
        "keystone-manage", "bootstrap",
        "--bootstrap-password", admin_password,
        "--bootstrap-admin-url", identity_url,
        "--bootstrap-internal-url", identity_url,
        "--bootstrap-public-url", identity_url,
        "--bootstrap-region-id", os_region_name
]
    print()

    if not run_command(bootstrap_cmd, "Bootstrapping Keystone...") : return False

    return True
    
def finalize(config):

    print()

    ip_address = get(config, "network.HOST_IP")

    if not run_command(["systemctl", "restart", "apache2"], "Restarting Apache2...") : return False

    if service_exists("keystone.service"):
        if not run_command(["systemctl", "restart", "keystone"], "Restarting Keystone...") : return False
     
    if not nc_wait(ip_address, 5000) : return False

    return True
    
def create_projects_and_demo_user(config, env):

    print()

    demo_password = get(config, "passwords.DEMO_PASSWORD")

    create_service_project_cmd = ["openstack", "project", "create", "--domain", "default", "--description", "Service Project", "service", "--or-show"]

    create_demo_user_cmds =  " && ".join([
        'openstack project create --domain default --description "Demo Project" demo --or-show',
        f'openstack user create --domain default --password {demo_password} demo --or-show',
        'openstack role create user --or-show',
        'openstack role add --project demo --user demo user'
    ])

    if not os_run(create_service_project_cmd, "Creating service project...", env=env) : return False
    
    if not run_command(["bash", "-c", create_demo_user_cmds], "Creating demo user...", env=env): return False    

    return True

def create_services_users(config, env):

    print()

    service_password = get(config, "passwords.SERVICE_PASSWORD")
    install_cinder = get(config, "optional_services.INSTALL_CINDER", "no").lower() == "yes"

    services_user_create_cmds = [
        f"openstack user create --domain default --password {service_password} glance --or-show",
        f"openstack user create --domain default --password {service_password} placement --or-show",
        f"openstack user create --domain default --password {service_password} nova --or-show",
        f"openstack user create --domain default --password {service_password} neutron --or-show",
    ]

    services_create_cmds = [
        'openstack service show glance || openstack service create --name glance --description "OpenStack Image" image',
        'openstack service show placement || openstack service create --name placement --description "Placement API" placement',
        'openstack service show nova || openstack service create --name nova --description "OpenStack Compute" compute',
        'openstack service show neutron || openstack service create --name neutron --description "OpenStack Networking" network',
    ]

    services_role_add_cmds = [
         "openstack role add --project service --user glance admin || true",
         "openstack role add --project service --user placement admin || true",
         "openstack role add --project service --user nova admin || true",
         "openstack role add --project service --user neutron admin || true",
    ]

    if install_cinder:
        services_user_create_cmds.append(f"openstack user create --domain default --password {service_password} cinder --or-show")
        services_create_cmds.append('openstack service show cinderv3 || openstack service create --name cinderv3 --description "OpenStack Block Storage" volumev3')
        services_role_add_cmds.append("openstack role add --project service --user cinder admin || true")

    services_user_create_full_cmd = " && ".join(services_user_create_cmds)
    services_create_cmds_full_cmd = " && ".join(services_create_cmds)
    services_role_add_cmds_full_cmd = " && ".join(services_role_add_cmds)

    if not run_command(["bash", "-c", services_user_create_full_cmd], "Creating services users...",env=env) : return False
    
    if not run_command(["bash", "-c", services_create_cmds_full_cmd], "Creating services...", env=env) : return False

    if not run_command(["bash", "-c", services_role_add_cmds_full_cmd], "Assigning services user roles...", env=env) : return False

    return True

def create_services_endpoints(config, env):

    ip_address = get(config, "network.HOST_IP")
    install_cinder = get(config, "optional_services.INSTALL_CINDER", "no").lower() == "yes"
    os_region_name = get(config, "openstack.REGION_NAME")

    def ep(service, interface, url):
        return (
            f"openstack endpoint create --region {os_region_name} "
            f"{service} {interface} '{url}'"
        )

    commands = [
        ep("image", "public",   f"http://{ip_address}:9292"),
        ep("image", "internal", f"http://{ip_address}:9292"),
        ep("image", "admin",    f"http://{ip_address}:9292"),

        ep("placement", "public",   f"http://{ip_address}:8778"),
        ep("placement", "internal", f"http://{ip_address}:8778"),
        ep("placement", "admin",    f"http://{ip_address}:8778"),

        ep("compute", "public",   f"http://{ip_address}:8774/v2.1"),
        ep("compute", "internal", f"http://{ip_address}:8774/v2.1"),
        ep("compute", "admin",    f"http://{ip_address}:8774/v2.1"),

        ep("network", "public",   f"http://{ip_address}:9696"),
        ep("network", "internal", f"http://{ip_address}:9696"),
        ep("network", "admin",    f"http://{ip_address}:9696"),
    ]

    if install_cinder:
        cinder_url = f"http://{ip_address}:8776/v3/%(project_id)s"
        commands += [
            ep("volumev3", "public",   cinder_url),
            ep("volumev3", "internal", cinder_url),
            ep("volumev3", "admin",    cinder_url),
        ]

    full_cmd = " && ".join(commands)

    if not run_command(["bash", "-c", full_cmd], "Creating services endpoints...", env=env) : return False

    return True

def generate_environment_cli_scripts(config):
     
    ip_address = get(config, "network.HOST_IP")

    admin_password = get(config, "passwords.ADMIN_PASSWORD")
    demo_password = get(config, "passwords.DEMO_PASSWORD")
     
    admin_openrc_content=f"""
export OS_PROJECT_DOMAIN_NAME=Default
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_NAME=admin
export OS_USERNAME=admin
export OS_PASSWORD={admin_password}
export OS_AUTH_URL=http://{ip_address}:5000/v3
export OS_IDENTITY_API_VERSION=3
export OS_IMAGE_API_VERSION=2
     """
    
    demo_openrc_content=f"""
export OS_PROJECT_DOMAIN_NAME=Default
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_NAME=demo
export OS_USERNAME=demo
export OS_PASSWORD={demo_password}
export OS_AUTH_URL=http://{ip_address}:5000/v3
export OS_IDENTITY_API_VERSION=3
export OS_IMAGE_API_VERSION=2
"""
    try:
        with open("/root/admin-openrc.sh", "w") as fadmin:
            fadmin.write(admin_openrc_content.strip())
        with open("/root/demo-openrc.sh", "w") as fdemo:
            fdemo.write(demo_openrc_content.strip())
        os.chmod("/root/admin-openrc.sh", 0o600)
        os.chmod("/root/demo-openrc.sh", 0o600)
    except Exception as e:
        print(f"{colors.RED}Failed to generate credentials scripts: {e}{colors.RESET}")
        return False

    return True

def run_setup_keystone(config, env):

    if not install_pkgs(): return False  
    if not conf_keystone(config): return False
    if not finalize(config): return False 
    if not create_projects_and_demo_user(config, env): return False 
    if not create_services_users(config, env): return False  
    if not create_services_endpoints(config, env): return False  
    if not generate_environment_cli_scripts(config): return False
    
    print(f"\n{colors.GREEN}Keystone configured successfully!{colors.RESET}\n")
    return True