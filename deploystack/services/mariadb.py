import os

from ..utils.core.commands import run_command
from ..utils.apt.apt import apt_install
from ..utils.config.parser import get
from ..utils.core.system_utils import nc_wait
from ..utils.core import colors
from ..templates import MYSQL_CONFIG

mysqld_file_path = "/etc/mysql/mariadb.conf.d/99-openstack.cnf"

def install_pkgs():
    
    packages = ["mariadb-server", "python3-pymysql"]

    if not apt_install(packages, ux_text=f"Installing MariaDB packages...") : return False

    return True

def conf_mariadb(config):

    ip_address = get(config, "network.HOST_IP", None)

    try:

        with open(MYSQL_CONFIG, "r") as f:
            template = f.read()
            mysqld_template_content = template.format(
                ip_address=ip_address,
            )

        with open(mysqld_file_path, "w") as f:
            f.write(mysqld_template_content)
    except Exception as e:
        print(f"\n{colors.RED}Unable to configure MariaDB with an unhandled exception: {e}{colors.RESET}")
        return False
    
    return True

def finalize(config):

    ip_address = get(config, "network.HOST_IP")
     
    restart_cmd = ["systemctl", "restart", "mysql"]

    if not run_command(restart_cmd, "Restarting MySQL...") : return False

    if not nc_wait(ip_address, 3306) : return False

    return True

def create_services_databases(config):

    print()
    
    db_password = get(config, "passwords.DATABASE_PASSWORD")
    ip_address = get(config, "network.HOST_IP")

    install_cinder = get(config, "optional_services.INSTALL_CINDER", "no") == "yes"

    databases = ["keystone", "glance", "placement", "nova_api", "nova_cell0", "nova", "neutron"]
    
    if install_cinder:
        databases.append("cinder")

    sql_commands = []

    for db in databases:
        sql_commands.append(f"CREATE DATABASE IF NOT EXISTS {db};")

    users = {
        "keystone": ["keystone"],
        "glance": ["glance"],
        "placement": ["placement"],
        "nova_api": ["nova"],
        "nova_cell0": ["nova"],
        "nova": ["nova"],
        "neutron": ["neutron"]
    }
    if install_cinder:
        users["cinder"] = ["cinder"]

    for db, usernames in users.items():
        for user in usernames:
            for host in ["localhost", "%", ip_address]:
                sql_commands.append(
                    f"CREATE USER IF NOT EXISTS '{user}'@'{host}' IDENTIFIED BY '{db_password}';"
                )
                sql_commands.append(
                    f"GRANT ALL PRIVILEGES ON {db}.* TO '{user}'@'{host}';"
                )

    sql_commands.append("FLUSH PRIVILEGES;")

    sql_string = " ".join(sql_commands)

    if not run_command(["mysql", "-u", "root", "-e", sql_string], "Creating services databases...") : return False
    
    return True

def run_setup_mariadb(config):

    if not install_pkgs(): return False 
    if not conf_mariadb(config): return False  
    if not finalize(config): return False  
    if not create_services_databases(config): return False

    print(f"\n{colors.YELLOW}MariaDB and Databases configured successfully!{colors.RESET}\n")
    return True