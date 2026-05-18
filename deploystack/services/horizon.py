# Configure the Dashboard (Horizon)

import os
import re
import subprocess
import sys

from ..utils.core.commands import run_command
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import get
from ..utils.core.system_utils import nc_wait, is_debian
from ..utils.core import colors

settings_file = "/etc/openstack-dashboard/local_settings.py"
apache_conf = "/etc/apache2/conf-enabled/openstack-dashboard.conf"

resolv_conf = "/etc/resolv.conf"

def get_wsgi_path() -> str:
    try:
        result = subprocess.run(["dpkg", "-L", "openstack-dashboard"], capture_output=True, text=True, check=True)
        files = result.stdout.splitlines()

        wsgi_files = [f for f in files if f.endswith("wsgi.py")]

        if wsgi_files:
            return wsgi_files[0] 
        else:
            print(f"\n{colors.RED}Unable to find path to wsgi.py for Horizon{colors.RESET}")
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"\n{colors.RED}ERROR: {e}{colors.RESET}")
        sys.exit(1)

def set_memcached(settings_file="/etc/openstack-dashboard/local_settings.py", host="127.0.0.1", port=11211):
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            content = f.read()
    else:
        content = ""

    memcached_block = f"""CACHES = {{
    'default': {{
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '{host}:{port}',
    }}
}}"""

    if "CACHES = {" in content:

        content = re.sub(r"CACHES\s*=\s*\{.*\}\s*\}", memcached_block, content, flags=re.DOTALL)
    else:
        content += "\n" + memcached_block + "\n"

    with open(settings_file, "w") as f:
        f.write(content)

def write_resolv_conf(config, settings_file):
    public_subnet_dns_servers = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS")

    try:
        with open(settings_file, "r") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""

    with open(settings_file, "a") as f:
        for dns in public_subnet_dns_servers:
            line = f"nameserver {dns}\n"
            if line not in existing:
                f.write(line)

def install_pkgs():

    if not apt_update() : return False

    horizon_packages = ["openstack-dashboard"]

    if is_debian():
        horizon_packages.append("libapache2-mod-wsgi-py3")
    
    if not apt_install(horizon_packages, ux_text=f"Installing Horizon package...") : return False

    return True

def conf_horizon(config):
    ip_address = get(config, "network.HOST_IP")

    settings_to_set = {

        "OPENSTACK_HOST": f'"{ip_address}"',
        "OPENSTACK_KEYSTONE_URL": f'"http://{ip_address}:5000/v3"',
        "DEBUG": "False",
        "ALLOWED_HOSTS": "['*']",
        "WEBROOT": "'/dashboard/'",
        "DEFAULT_THEME": "'default'",
        "COMPRESS_OFFLINE": "False",
        "LOGIN_URL" : "'/dashboard/auth/login/'",
        "LOGOUT_URL" : "'/dashboard/auth/logout/'",
        "LOGIN_REDIRECT_URL" : "'/dashboard/'"
    }

    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            lines = f.readlines()
    else:
        lines = []

    existing_keys = {l.split("=")[0].strip() for l in lines if "=" in l}
    wsgi_path = get_wsgi_path()

    with open(settings_file, "w") as f:
        for line in lines:
            key_found = False
            for key, value in settings_to_set.items():
                if line.strip().startswith(key):
                    f.write(f"{key} = {value}\n")
                    key_found = True
                    break
            if not key_found:
                f.write(line)

        for key, value in settings_to_set.items():
            if key not in existing_keys:
                f.write(f"{key} = {value}\n")

    set_memcached(host="127.0.0.1", port=11211)

    if os.path.exists(apache_conf):
        os.remove(apache_conf)

    apache_block = f"""
WSGIScriptAlias /dashboard {wsgi_path} process-group=horizon
WSGIDaemonProcess horizon user=horizon group=horizon processes=3 threads=10 display-name=%{{GROUP}}
WSGIProcessGroup horizon
WSGIApplicationGroup %{{GLOBAL}}
Alias /static /var/lib/openstack-dashboard/static/
Alias /dashboard/static /var/lib/openstack-dashboard/static/
<Directory /usr/share/openstack-dashboard/openstack_dashboard>
  Require all granted
</Directory>
<Directory /var/lib/openstack-dashboard/static>
  Require all granted
</Directory>
"""

    if not os.path.exists(apache_conf) or apache_block not in open(apache_conf).read():
        with open(apache_conf, "a") as f:
            f.write(apache_block)


def finalize(config):

    print()

    ip_address = get(config, "network.HOST_IP")

    if not run_command(["systemctl", "restart", "apache2"], "Restarting Apache2..."): return False
    
    if not nc_wait(ip_address, 80) : return False

    return True

def run_setup_horizon(config):

    write_resolv_conf()

    if not install_pkgs(): return False
    conf_horizon(config)
    if not finalize(config): return False

    print(f"\n{colors.GREEN}Horizon configured successfully!{colors.RESET}")
    return True