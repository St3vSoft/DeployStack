# Configure the Identity service (Keystone)

import os
import json

from ..utils.core.commands import run_command, run_command_output, run_commands, run_command_sync
from ..utils.core.system_utils import service_exists, is_debian, nc_wait
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option
from ..utils.core import colors

from ..utils.config.helpers import parse_bool

from .patches.keystone.wsgi import patch_keystone_wsgi

from .utils import get_base_host
from .utils.openstack_repos import ensure_os_release

keystone_conf = "/etc/keystone/keystone.conf"

def _get_endpoints(env=None):

    raw = run_command_output(["openstack", "endpoint", "list", "-f", "json"], env=env)

    if raw is False:
            return False
    
    return json.loads(raw or "[]")

def _get_role_assignments(env=None):

    raw = run_command_output(["openstack", "role", "assignment", "list", "--names", "-f", "json"], env=env)

    if raw is False:
        return False

    return json.loads(raw or "[]")

def _get_services(env=None):
    
    raw = run_command_output(["openstack", "service", "list", "-f", "json"], env=env)

    if raw is False:
            return False

    return json.loads(raw or "[]")

def _ensure_user_password(env, name, password):

    if not name or not password: return False

    try:
        run_command_sync(["openstack", "user", "create", "--domain", "default", "--password", password, name, "--or-show"], env=env)

        run_command_sync(["openstack", "user", "set", "--password", password, name])

        return True

    except Exception as exc:
        return False

def install_pkgs():

    packages = ["keystone", "apache2"]

    if not apt_install(packages, ux_text=f"Installing Keystone packages...") : return False

    return True

def conf_keystone(config):

    print()

    ip_address = get(config, "network.HOST_IP")
      
    db_password = get(config, "passwords.DATABASE_PASSWORD")

    admin_password = get(config, "passwords.ADMIN_PASSWORD")

    os_region_name = get(config, "openstack.REGION_NAME")

    identity_url = f"http://{get_base_host(config)}:5000/v3/"

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

    if ensure_os_release(config, "flamingo"):
        if not patch_keystone_wsgi() : return False

    if not run_command(["systemctl", "restart", "apache2"], "Restarting Apache2...") : return False

    if service_exists("keystone.service") and is_debian():
        if not run_command(["systemctl", "restart", "keystone"], "Restarting Keystone...") : return False
     
    if not nc_wait(ip_address, 5000) : return False

    return True
    
def create_projects_and_demo_user(config, env):

    print()

    demo_password = get(config, "passwords.DEMO_PASSWORD")

    assignments = _get_role_assignments(env)

    if assignments is False: return False

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
        create_demo_user_cmds.append(["openstack", "role", "add", "--project", "demo", "--user", "demo", "user"])

    if ("demo", "demo", "reader") not in existing_assignments:
        create_demo_user_cmds.append(["openstack", "role", "add", "--project", "demo", "--user", "demo", "reader"])

    if ("demo", "demo", "member") not in existing_assignments:
        create_demo_user_cmds.append(["openstack", "role", "add", "--project", "demo", "--user", "demo", "member"])

    if not run_command(create_service_project_cmd, "Creating service project...", env=env): return False

    if not run_commands(create_demo_user_cmds, "Creating demo user...", env=env): return False  

    return True

def create_services_users(config, env):

    print()

    service_password = get(config, "passwords.SERVICE_PASSWORD")
    if not service_password:
        return False

    install_cinder = parse_bool(get(config, "optional_services.INSTALL_CINDER"), False)
    install_manila = parse_bool(get(config, "optional_services.INSTALL_MANILA"), False)

    services_users = ["glance", "placement", "nova", "neutron"]
    if install_cinder:
        services_users.append("cinder")
    if install_manila:
        services_users.append("manila")

    assignments = _get_role_assignments(env)
    existing = {(a["User"], a["Project"], a["Role"]) for a in assignments}

    user_cmds = [["openstack", "user", "create", "--domain", "default", "--password", service_password, user, "--or-show"] for user in services_users]

    role_cmds = []

    for user in services_users:
        roles = ["admin"]
        if user in ("nova", "cinder"):
            roles.append("service")

        for role in roles:
            if (user, "service", role) not in existing:
                role_cmds.append([
                    "openstack", "role", "add",
                    "--project", "service", "--user", user, role
                ])

    if not run_commands(user_cmds, "Creating services users...", env=env):
        return False

    for user in services_users:
        if not _ensure_user_password(env, user, service_password):
            return False

    if not run_commands(role_cmds, "Assigning services user roles...", env=env):
        return False

    return True

def create_services_entities(config, env):

    print()

    install_cinder = parse_bool(get(config, "optional_services.INSTALL_CINDER"), False)
    install_manila = parse_bool(get(config, "optional_services.INSTALL_MANILA"), False)

    services = _get_services(env)
    if services is False:
        return False

    existing = {(s.get("Name") or s.get("name"), s.get("Type") or s.get("type")) for s in services}

    entities = [
        ("glance", "OpenStack Image", "image"),
        ("placement", "Placement API", "placement"),
        ("nova", "OpenStack Compute", "compute"),
        ("neutron", "OpenStack Networking", "network"),
    ]

    if install_cinder:
        entities.append(("cinderv3", "OpenStack Block Storage", "volumev3"))

    if install_manila:
        entities.extend(
            [("manilav2", "OpenStack Shared File Systems V2", "sharev2")]
            if ensure_os_release(config, ["gazpacho", "hibiscus"])
            else [
                ("manila", "OpenStack Shared File Systems", "share"),
                ("manilav2", "OpenStack Shared File Systems V2", "sharev2"),
            ]
        )

    commands = [
        ["openstack", "service", "create",
         "--name", name, "--description", description, type_]
        for name, description, type_ in entities
        if (name, type_) not in existing
    ]

    return run_commands(commands, "Creating services entities...", env=env)

def create_services_endpoints(config, env):

    print()

    install_cinder = parse_bool(get(config, "optional_services.INSTALL_CINDER"), False)
    install_manila = parse_bool(get(config, "optional_services.INSTALL_MANILA"), False)

    region = get(config, "openstack.REGION_NAME")
    host = get_base_host(config)

    endpoints = _get_endpoints(env=env)
    if endpoints is False:
        return False

    existing = {
        (e["Service Type"], e["Interface"], e["Region"], e["URL"])
        for e in endpoints
    }

    services = [
        ("image", f"http://{host}:9292"),
        ("placement", f"http://{host}:8778"),
        ("compute", f"http://{host}:8774/v2.1"),
        ("network", f"http://{host}:9696"),
    ]

    if install_cinder:
        services.append(("volumev3", f"http://{host}:8776/v3/%(project_id)s"))

    if install_manila:
        if ensure_os_release(config, ["gazpacho", "hibiscus"]):
            services.append(("sharev2", f"http://{host}:8786/v2"))
        else:
            services.extend([
                ("share", f"http://{host}:8786/v1/%(tenant_id)s"),
                ("sharev2", f"http://{host}:8786/v2"),
            ])

    commands = [
        [
            "openstack", "endpoint", "create",
            "--region", region,
            service, interface, url
        ]
        for service, url in services
        for interface in ("public", "internal", "admin")
        if (service, interface, region, url) not in existing
    ]

    return run_commands(commands, "Creating services endpoints...", env=env)

def generate_environment_cli_scripts(config):
     
    admin_password = get(config, "passwords.ADMIN_PASSWORD")
    demo_password = get(config, "passwords.DEMO_PASSWORD")
     
    admin_openrc_content=f"""
export OS_PROJECT_DOMAIN_NAME=Default
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_NAME=admin
export OS_USERNAME=admin
export OS_PASSWORD={admin_password}
export OS_AUTH_URL=http://{get_base_host(config)}:5000/v3
export OS_IDENTITY_API_VERSION=3
export OS_IMAGE_API_VERSION=2
     """
    
    demo_openrc_content=f"""
export OS_PROJECT_DOMAIN_NAME=Default
export OS_USER_DOMAIN_NAME=Default
export OS_PROJECT_NAME=demo
export OS_USERNAME=demo
export OS_PASSWORD={demo_password}
export OS_AUTH_URL=http://{get_base_host(config)}:5000/v3
export OS_IDENTITY_API_VERSION=3
export OS_IMAGE_API_VERSION=2
"""
    
    try:
        paths = [
            "/root/admin-openrc.sh",
            "/var/lib/deploystack/admin-openrc"
        ]
        for path in paths:
            with open(path, "w") as fadmin:
                fadmin.write(admin_openrc_content.strip())
                os.chmod(path, 0o600)

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

    if not create_services_entities(config, env) : return False

    if not create_services_endpoints(config, env): return False  

    if not generate_environment_cli_scripts(config): return False
    
    print(f"\n{colors.GREEN}Keystone configured successfully!{colors.RESET}\n")
    return True