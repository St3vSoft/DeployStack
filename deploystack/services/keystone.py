# Configure the Identity service (Keystone)

import os
import json
import subprocess

from ..utils.core.commands import run_command, os_run_output, run_command_output, run_commands
from ..utils.core.system_utils import service_exists, is_debian 
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option
from ..utils.core.system_utils import nc_wait
from ..utils.core import colors

keystone_conf = "/etc/keystone/keystone.conf"

def get_endpoints(env=None):
    raw = run_command_output(["openstack", "endpoint", "list", "-f", "json"], env=env)
    return json.loads(raw or "[]")

def get_role_assignments(env=None):
    raw = run_command_output(
        ["openstack", "role", "assignment", "list", "--names", "-f", "json"],
        env=env
    )
    return json.loads(raw or "[]")

def get_services(env=None):
    raw = run_command_output(
        ["openstack", "service", "list", "-f", "json"],
        env=env
    )

    return json.loads(raw or "[]")

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

    if service_exists("keystone.service") and is_debian():
        if not run_command(["systemctl", "restart", "keystone"], "Restarting Keystone...") : return False
     
    if not nc_wait(ip_address, 5000) : return False

    return True
    
def create_projects_and_demo_user(config, env):

    print()

    demo_password = get(config, "passwords.DEMO_PASSWORD")

    assignments = get_role_assignments(env)

    existing_assignments = {(a["User"], a["Project"], a["Role"]) for a in assignments}

    create_service_project_cmd = [
        "openstack", "project", "create",
        "--domain", "default",
        "--description", "Service Project",
        "service", "--or-show"
    ]

    create_demo_user_cmds = [
        ["openstack", "project", "create", "--domain", "default", "--description", "Demo Project", "demo", "--or-show"],
        ["openstack", "user", "create", "--domain", "default", "--password", demo_password, "demo", "--or-show"],
        ["openstack", "role", "create", "user", "--or-show"],
    ]

    if ("demo", "demo", "user") not in existing_assignments:
        create_demo_user_cmds.append(
            ["openstack", "role", "add", "--project", "demo", "--user", "demo", "user"]
        )

    if not run_command(create_service_project_cmd, "Creating service project...", env=env): return False

    if not run_commands(create_demo_user_cmds, "Creating demo user...", env=env): return False  

    return True

def create_services_users(config, env):

    print()

    service_password = get(config, "passwords.SERVICE_PASSWORD")
    install_cinder = get(config, "optional_services.INSTALL_CINDER", "no").lower() == "yes"

    services = get_services(env)
    assignments = get_role_assignments(env)

    services_user_create_cmds = [
        ["openstack", "user", "create", "--domain", "default", "--password", service_password, "glance", "--or-show"],
        ["openstack", "user", "create", "--domain", "default", "--password", service_password, "placement", "--or-show"],
        ["openstack", "user", "create", "--domain", "default", "--password", service_password, "nova", "--or-show"],
        ["openstack", "user", "create", "--domain", "default", "--password", service_password, "neutron", "--or-show"],
    ]

    services_create_cmds = []
    services_role_add_cmds = []

    existing_assignments = {
        (
            a["User"],
            a["Project"],
            a["Role"]
        )
        for a in assignments
    }

    existing_services = {
        s.get("Name") or s.get("name")
        for s in services
    }

    if "glance" not in existing_services:
        services_create_cmds.append(["openstack", "service", "create", "--name", "glance", "--description", "OpenStack Image", "image"])

    if "placement" not in existing_services:
        services_create_cmds.append(["openstack", "service", "create", "--name", "placement", "--description", "Placement API", "placement"])

    if "nova" not in existing_services:
        services_create_cmds.append(["openstack", "service", "create", "--name", "nova", "--description", "OpenStack Compute", "compute"])

    if "neutron" not in existing_services:
        services_create_cmds.append(["openstack", "service", "create", "--name", "neutron", "--description", "OpenStack Networking", "network"])

    if ("glance", "service", "admin") not in existing_assignments:
        services_role_add_cmds.append(["openstack", "role", "add", "--project", "service", "--user", "glance", "admin"])

    if ("placement", "service", "admin") not in existing_assignments:
        services_role_add_cmds.append(["openstack", "role", "add", "--project", "service", "--user", "placement", "admin"])

    if ("nova", "service", "admin") not in existing_assignments:
        services_role_add_cmds.append(["openstack", "role", "add", "--project", "service", "--user", "nova", "admin"])

        if ("nova", "service", "service") not in existing_assignments:
            services_role_add_cmds.append(["openstack", "role", "add", "--user", "nova", "--project", "service", "service"])

    if ("neutron", "service", "admin") not in existing_assignments:
        services_role_add_cmds.append(["openstack", "role", "add", "--project", "service", "--user", "neutron", "admin"])

    if install_cinder:

        services_user_create_cmds.append(["openstack", "user", "create", "--domain", "default", "--password", service_password, "cinder", "--or-show"])

        if "cinderv3" not in existing_services:
            services_create_cmds.append(["openstack", "service", "create", "--name", "cinderv3", "--description", "OpenStack Block Storage", "volumev3"])

        if ("cinder", "service", "admin") not in existing_assignments:
            services_role_add_cmds.append(["openstack", "role", "add", "--project", "service", "--user", "cinder", "admin"])

            if ("cinder", "service", "service") not in existing_assignments:
                services_role_add_cmds.append(["openstack", "role", "add", "--user", "cinder", "--project", "service", "service"])

    if not run_commands(services_user_create_cmds, "Creating services users...", env=env) : return False

    if not run_commands(services_create_cmds, "Creating services...", env=env) : return False

    if not run_commands(services_role_add_cmds, "Assigning services user roles...", env=env) : return False

    return True

def create_services_endpoints(config, env):

    print()
  
    ip_address = get(config, "network.HOST_IP")
    install_cinder = get(config, "optional_services.INSTALL_CINDER", "no").lower() == "yes"
    os_region_name = get(config, "openstack.REGION_NAME")

    glance_url = f"http://{ip_address}:9292"

    placement_url = f"http://{ip_address}:8778"
    nova_url = f"http://{ip_address}:8774/v2.1"
    neutron_url = f"http://{ip_address}:9696"

    endpoints = get_endpoints(env=env)

    endpoints_create_cmds = []

    existing_endpoints = {
        (
            a["Service Type"],
            a["Interface"],
            a["Region"],
            a["URL"],
        )
        for a in endpoints
    }

    if ("image", "public", os_region_name, glance_url) not in existing_endpoints:
        endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "image", "public", glance_url])

    if ("image", "internal", os_region_name, glance_url) not in existing_endpoints:
        endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "image", "internal", glance_url])

    if ("image", "admin", os_region_name, glance_url) not in existing_endpoints:
        endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "image", "admin", glance_url])

    if ("placement", "public", os_region_name, placement_url) not in existing_endpoints:
        endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "placement", "public", placement_url])

    if ("placement", "internal", os_region_name, placement_url) not in existing_endpoints:
        endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "placement", "internal", placement_url])

    if ("placement", "admin", os_region_name, placement_url) not in existing_endpoints:
        endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "placement", "admin", placement_url])
    
    if ("compute", "public", os_region_name, nova_url) not in existing_endpoints:
         endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "compute", "public", nova_url])

    if ("compute", "internal", os_region_name, nova_url) not in existing_endpoints:
         endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "compute", "internal", nova_url])

    if ("compute", "admin", os_region_name, nova_url) not in existing_endpoints:
         endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "compute", "admin", nova_url])

    if ("network", "public", os_region_name, nova_url) not in existing_endpoints:
         endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "compute", "public", neutron_url])
    
    if ("network", "internal", os_region_name, nova_url) not in existing_endpoints:
         endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "compute", "internal", neutron_url])

    if ("network", "admin", os_region_name, nova_url) not in existing_endpoints:
         endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "compute", "admin", neutron_url])

    if install_cinder:
        cinder_url = f"http://{ip_address}:8776/v3/%(project_id)s"

        if ("volumev3", "public", os_region_name, nova_url) not in existing_endpoints:
            endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "volumev3", "public", cinder_url])
    
        if ("volumev3", "internal", os_region_name, nova_url) not in existing_endpoints:
            endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "volumev3", "internal", cinder_url])

        if ("volumev3", "admin", os_region_name, nova_url) not in existing_endpoints:
            endpoints_create_cmds.append(["openstack", "endpoint", "create", "--region", os_region_name, "volumev3", "admin", cinder_url])

    #endpoints_create_cmds = [cmd for cmd in endpoints_create_cmds if cmd is not None]

    if not run_commands(endpoints_create_cmds, "Creating services endpoints...", env=env) : return False

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