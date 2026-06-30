# Configure the Dashboard (Horizon)

import os
import pwd
import grp
import re
import shutil
import tempfile

from ..utils.core.commands import run_command
from ..utils.apt.apt import apt_install, apt_update
from ..utils.config.parser import get
from ..utils.core.system_utils import nc_wait, is_debian
from ..utils.core import colors

settings_file = "/etc/openstack-dashboard/local_settings.py"

ubuntu_apache_conf = "/etc/apache2/conf-enabled/openstack-dashboard.conf"
debian_apache_conf = "/etc/apache2/sites-enabled/openstack-dashboard-alias-only.conf"

resolv_conf = "/etc/resolv.conf"

debian_apache_block = """
WSGIDaemonProcess horizon user=www-data group=www-data threads=5
WSGIScriptAlias /horizon /usr/share/openstack-dashboard/wsgi.py process-group=horizon application-group=%{GLOBAL}
Alias /static /var/lib/openstack-dashboard/static
Alias /horizon/static /var/lib/openstack-dashboard/static

<Directory /usr/share/openstack-dashboard>
    Require all granted
</Directory>

<Directory /var/lib/openstack-dashboard/static>
    Require all granted
</Directory>
"""

ubuntu_apache_block = """
WSGIScriptAlias /dashboard /usr/share/openstack-dashboard/openstack_dashboard/wsgi.py process-group=horizon
WSGIDaemonProcess horizon user=horizon group=horizon processes=3 threads=10 display-name=%{GROUP}
WSGIProcessGroup horizon
WSGIApplicationGroup %{GLOBAL}
Alias /static /var/lib/openstack-dashboard/static/
Alias /dashboard/static /var/lib/openstack-dashboard/static/

<Directory /usr/share/openstack-dashboard/openstack_dashboard>
    Require all granted
</Directory>

<Directory /var/lib/openstack-dashboard/static>
    Require all granted
</Directory>
"""

def atomic_write(path, content):
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_name) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    shutil.move(tmp_path, path)

def set_memcached(settings_file=settings_file, host="127.0.0.1", port=11211):

    content = ""
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            content = f.read()

    memcached_block = f"""
CACHES = {{
    'default': {{
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '{host}:{port}',
    }}
}}
"""

    pattern = r"CACHES\s*=\s*\{.*?\}\s*\}"
    if re.search(pattern, content, flags=re.DOTALL):
        content = re.sub(pattern, memcached_block, content, flags=re.DOTALL)
    else:
        content += "\n" + memcached_block + "\n"

    atomic_write(settings_file, content)

def write_resolv_conf(config):
    dns_servers = get(config, "network.HOST_DNS_SERVERS") or []

    if not dns_servers:
        return True

    try:
        with open(resolv_conf, "r") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""

    lines_to_add = []
    for dns in dns_servers:
        line = f"nameserver {dns}\n"
        if line not in existing:
            lines_to_add.append(line)

    if not lines_to_add:
        return True

    with open(resolv_conf, "a") as f:
        f.writelines(lines_to_add)

    return True

def install_pkgs():
    if not apt_update():
        return False

    packages = ["openstack-dashboard-apache"] if is_debian() else ["openstack-dashboard"]

    return apt_install(packages, ux_text="Installing Horizon package...")

def conf_horizon(config):
    ip_address = get(config, "network.HOST_IP")
    if not ip_address:
        print(f"{colors.RED}Missing HOST_IP{colors.RESET}")
        return False

    settings_to_set = {
        "OPENSTACK_HOST": f'"{ip_address}"',
        "OPENSTACK_KEYSTONE_URL": f'"http://{ip_address}:5000/v3"',
        "DEBUG": "False",
        "ALLOWED_HOSTS": "['*']",
        "DEFAULT_THEME": "'default'",
        "COMPRESS_OFFLINE": "False",
    }

    settings_to_set["WEBROOT"] = "'/horizon/'" if is_debian() else "'/dashboard/'"

    content = ""
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            content = f.read()

    for key, value in settings_to_set.items():
        pattern = rf"^{key}\s*=.*$"
        replacement = f"{key} = {value}"
        if re.search(pattern, content, flags=re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            content += "\n" + replacement + "\n"

    atomic_write(settings_file, content)

    set_memcached(host="127.0.0.1", port=11211)

    apache_conf = debian_apache_conf if is_debian() else ubuntu_apache_conf
    apache_block = debian_apache_block if is_debian() else ubuntu_apache_block

    atomic_write(apache_conf, apache_block)

    path = "/etc/openstack-dashboard/local_settings.py"
    directory = "/etc/openstack-dashboard"

    uid = pwd.getpwnam("root").pw_uid
    gid = grp.getgrnam("root").gr_gid

    uid = pwd.getpwnam("root").pw_uid
    gid = grp.getgrnam("root").gr_gid

    os.chown(path, uid, gid)
    os.chown(directory, uid, gid)

    os.chmod(path, 0o644)
    os.chmod(directory, 0o755)

    return True

def finalize(config):
    ip_address = get(config, "network.HOST_IP")
    if not ip_address:
        return False

    if is_debian():
        print()

        run_command(["a2enmod", "ssl"], "Enabling SSL Module...")
        run_command(["make-ssl-cert", "generate-default-snakeoil", "--force-overwrite"],
                    "Regenerating SSL Certificates...")

    run_command(["systemctl", "restart", "apache2"], "Restarting Apache2...")

    return nc_wait(ip_address, 80)

def run_setup_horizon(config):
    write_resolv_conf(config)

    if not install_pkgs():
        return False

    if not conf_horizon(config):
        return False

    if not finalize(config):
        return False

    print(f"\n{colors.GREEN}Horizon configured successfully!{colors.RESET}")
    return True