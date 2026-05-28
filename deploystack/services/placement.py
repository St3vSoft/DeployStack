# Configure the Placement service (Placement)

from ..utils.core.commands import run_command
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.config.setter import set_conf_option
from ..utils.core.system_utils import nc_wait
from ..utils.core import colors
from ..utils.core.system_utils import service_exists, is_debian

placement_conf = "/etc/placement/placement.conf"

def install_pkgs():

    packages = ["placement-api"]

    if not apt_install(packages, ux_text=f"Installing Placement package..."): return False
    
    return True

def conf_placement(config):

    print()

    db_password = get(config, "passwords.DATABASE_PASSWORD")
    service_password = get(config, "passwords.SERVICE_PASSWORD")

    ip_address = get(config, "network.HOST_IP")

    os_region_name = get(config, "openstack.REGION_NAME")

    set_conf_option(placement_conf, "placement_database", "connection", f"mysql+pymysql://placement:{db_password}@{ip_address}/placement")
      
    set_conf_option(placement_conf, "keystone_authtoken", "www_authenticate_uri", f"http://{ip_address}:5000/")
    set_conf_option(placement_conf, "keystone_authtoken", "auth_url", f"http://{ip_address}:5000/")
    set_conf_option(placement_conf, "keystone_authtoken", "region_name", os_region_name)
    set_conf_option(placement_conf, "keystone_authtoken", "memcached_servers", "127.0.0.1:11211")
    set_conf_option(placement_conf, "keystone_authtoken", "auth_type", "password")
    set_conf_option(placement_conf, "keystone_authtoken", "project_domain_name", "Default")
    set_conf_option(placement_conf, "keystone_authtoken", "user_domain_name", "Default")
    set_conf_option(placement_conf, "keystone_authtoken", "project_name", "service")
    set_conf_option(placement_conf, "keystone_authtoken", "username", "placement")
    set_conf_option(placement_conf, "keystone_authtoken", "password", service_password)

    set_conf_option(placement_conf, "api", "auth_strategy", "keystone")

    if not run_command([
    "sudo", "-u", "placement",
    "placement-manage", "db", "sync"
    ], "Running Placement DB Migrations...") : return False
    
    return True

def finalize(config):

    print()
    
    ip_address = get(config, "network.HOST_IP")    

    placement_service = []

    if service_exists("placement-api.service") and is_debian():
        placement_service.append("placement-api")
    else:
        placement_service.append("apache2")

    if not run_command(["systemctl", "restart"] + placement_service, "Restarting Apache2..."): return False
    
    if not nc_wait(ip_address, 8778) : return False

    return True

def run_setup_placement(config):
     
    if not install_pkgs(): return False   
    if not conf_placement(config): return False  
    if not finalize(config): return False
    
    print(f"\n{colors.GREEN}Placement configured successfully!{colors.RESET}\n")
    return True