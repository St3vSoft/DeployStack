import subprocess
import os
import sys
import time
import uuid
import shutil
import base64
import json
from passlib.hash import sha512_crypt

from ...utils.core import colors
from ...templates import CLOUD_CONFIG_LINUX, CLOUD_CONFIG_LINUX_NO_ROOT

from ..shell import _run, _os, _os_value, logger

SSH_KEY_PATH = os.path.expanduser("~/.ssh/")
DEFAULT_FLAVOR  = "m1.tiny"
DEFAULT_IMAGE   = "cirros"
DEFAULT_NETWORK = "internal"
EXTERNAL_NET    = "public"

def ensure_keypair(key_path: str = SSH_KEY_PATH, name: str = None) -> str:

    keypair_name = f"{name}-keypair"

    if not os.path.isfile(key_path):
        print(f"Creating local '{keypair_name}' ssh key at {key_path}")
        subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "2048", "-N", "", "-f", key_path],
            check=True, stdout=subprocess.DEVNULL
        )
    else:
        print(f"SSH key already exists: {key_path}")

    pub_key_path = key_path + ".pub"

    existing = _os("keypair", "list", "-f", "value", "-c", "Name")
    if keypair_name not in existing.splitlines():
        print(f"Registering keypair '{keypair_name}' in OpenStack ...\n")
        _os("keypair", "create", "--public-key", pub_key_path, keypair_name)
    else:
        print(f"Keypair '{keypair_name}' already exists in OpenStack")

    return keypair_name


def get_image_properties(image_id: str) -> dict:
    import json

    out = _os("image", "show", image_id, "-f", "json")
    data = json.loads(out)
    props = data.get("properties") or {}

    return {
        "name":         data.get("name"),
        "os_distro":    props.get("os_distro", "").lower(),
        "os_type":      props.get("os_type", "").lower(),
        "os_version":   props.get("os_version"),
        "os_admin_user": props.get("os_admin_user")
    }


def get_default_image(preferred: str) -> str:
    out = _os("image", "list", "--status", "active", "-f", "value", "-c", "ID", "-c", "Name")
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        image_id, image_name = parts
        if preferred.lower() == image_name.lower():

            return image_id

    logger.error(f"{colors.RED}No active image found with name '{preferred}'{colors.RESET}")
    sys.exit(1)

def get_default_flavor(preferred: str = DEFAULT_FLAVOR) -> str:
    out = _os("flavor", "list", "-f", "value", "-c", "ID", "-c", "Name")
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and preferred.lower() in parts[1].lower():
            return parts[0]
    return out.splitlines()[0].split()[0] if out else "1"

def delete_instance(instance_id: str):

    try:
        subprocess.run(
            ["openstack", "server", "delete", instance_id],
            check=True
        )
    except subprocess.CalledProcessError as e:
            print(f"Error when deleting instance {instance_id}: {e}")

def internal_router_has_gateway() -> bool:
    result = _run(["openstack", "router", "show", "internal_router", "-f", "json", "-c", "external_gateways"])
    external_gateways = json.loads(result.stdout)

    gateways = external_gateways.get("external_gateways", [])
    return bool(gateways)


def get_instance_ip(instance_name: str, network_name: str) -> str:
    result = _run(["openstack", "server list", "-f", "json"])
    servers = json.loads(result.stdout)
    
    for s in servers:
        if s["Name"] == instance_name:
            return s["Networks"].get(network_name, [None])[0]
    return None

def get_default_network(preferred: str | None = None) -> str:
    out = _os("network", "list", "-f", "value", "-c", "ID", "-c", "Name")
    lines = [line.split(None, 1) for line in out.splitlines() if line.strip()]

    if preferred:
        for net_id, net_name in lines:
            if preferred.lower() in net_name.lower():
                if not DEFAULT_NETWORK in net_name.lower():
                    logger.warning(f"{colors.YELLOW}The {net_name} network will be used, the floating IP assignment will be skipped{colors.RESET}\n")
                return net_id

    for net_id, net_name in lines:
        if "internal" in net_name.lower():
            return net_id

    for net_id, net_name in lines:
        if "public" not in net_name.lower():
            return net_id

    logger.error("No suitable internal network found. Cannot use public network by default.")
    sys.exit(1)

def get_server_id(name: str) -> str:
    """Resolve server name to ID. Fails if multiple servers share the same name."""
    out = _os("server", "list", "--name", f"^{name}$",
              "-f", "value", "-c", "ID", "-c", "Name")
    matches = [line.split(None, 1) for line in out.splitlines() if line.strip()]

    exact = [srv_id for srv_id, srv_name in matches if srv_name.strip() == name]

    if not exact:
        logger.error(f"No server found with name '{name}'")
        sys.exit(1)
    if len(exact) > 1:
        logger.error(
            f"Multiple servers found with name '{name}': {exact}\n"
            f"Use a unique name or pass the server ID directly."
        )
        sys.exit(1)
    return exact[0]


def get_floating_ip_id(fip_address: str) -> str:
    """Resolve floating IP address to its ID."""
    out = _os("floating", "ip", "list",
              "--floating-ip-address", fip_address,
              "-f", "value", "-c", "ID")
    fip_id = out.strip().splitlines()[0] if out.strip() else ""
    if not fip_id:
        logger.error(f"Floating IP {fip_address} not found")
        sys.exit(1)
    return fip_id


def generate_user_config(ostype: str, default_user: str, password: str,
                          public_key: str = None) -> str:

    password_b64 = base64.b64encode(password.encode('utf-16-le')).decode('ascii')

    windows_config_drive = f"""
$username = "{default_user}"
$passwordB64 = "{password_b64}"

# Decodifica Base64
$bytes = [System.Convert]::FromBase64String($passwordB64)
$password = [System.Text.Encoding]::Unicode.GetString($bytes)

$secure = ConvertTo-SecureString $password -AsPlainText -Force

Set-LocalUser -Name $username -Password $secure
Set-LocalUser -Name $username -PasswordNeverExpires $true
Enable-LocalUser -Name $username
"""

    password_hash = sha512_crypt.hash(password)

    template_path = (
        CLOUD_CONFIG_LINUX_NO_ROOT
        if default_user != "root"
        else CLOUD_CONFIG_LINUX
    )

    with open(template_path, "r") as f:
        template = f.read()
        linux_config_drive = template.format(
            default_user=default_user,
            password_hash=password_hash,
            public_key=public_key,
        )

    code = uuid.uuid4().hex
    base_path = f"/tmp/config_drive_{code}"
    openstack_path = os.path.join(base_path, "openstack", "latest")
    os.makedirs(openstack_path, exist_ok=True)

    ostype = (ostype or "").lower()

    if ostype == "windows":
        content = windows_config_drive
    elif ostype == "linux":
        content = linux_config_drive

    file_path = os.path.join(openstack_path, "user_data")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path


def create_server(name: str, image_id: str, flavor_id: str,
                  network_id: str, keypair_name: str) -> str:
    """Create server and return its ID."""

    server_id: str = None

    print(f"Launching instance '{name}' ...\n")

    try:

        result = _run([
            "openstack", "server", "create",
            "--image",    image_id,
            "--flavor",   flavor_id,
            "--network",  network_id,
            "--key-name", keypair_name,
            "--wait",
            "-f", "value", "-c", "id",
            name
        ])

        server_id = result.stdout.strip()
        if not server_id:
            logger.error("Server creation failed:\n" + result.stderr)
            sys.exit(1)

        return server_id
    
    except subprocess.CalledProcessError as e:

        out = subprocess.run(["openstack", "server", "list", "--long", "--status",  "ERROR",  "-f", "value", "-c", "ID", "-c", "Name"], capture_output=True, text=True, check=True)

        for line in out.stdout.splitlines():
            instance_id, instance_name = line.split(None, 1)
            if name in instance_name:
                 delete_instance(instance_id)

        logger.error(f"{colors.RED}OpenStack server creation command failed: {e}{colors.RESET}\n\nFor more information about the error, please see the log: /var/log/nova/nova-compute.log")
        sys.exit(1) 

def create_server_with_password(
    name: str,
    image_id: str,
    flavor_id: str,
    network_id: str,
    keypair_name: str,
    os_type: str,
    username: str,
    password: str,
    public_key: str = None,
) -> str:
    """Create server with cloud-init user config and return its ID."""

    config_drive_file_path = generate_user_config(os_type, username, password, public_key)

    server_id: str = None

    print(f"Launching instance '{name}' ...\n")

    try:
        result = _run([
            "openstack", "server", "create",
            "--image",        image_id,
            "--flavor",       flavor_id,
            "--network",      network_id,
            "--key-name",     keypair_name,
            "--config-drive", "true",
            "--user-data",    config_drive_file_path,
            "--wait",
            "-f", "value", "-c", "id",
            name
        ])

        server_id = result.stdout.strip()
        if not server_id:
            logger.error("Server creation failed:\n" + result.stderr)
            sys.exit(1)
        return server_id
    
    except subprocess.CalledProcessError as e:
        out = subprocess.run(["openstack", "server", "list", "--long", "--status",  "ERROR",  "-f", "value", "-c", "ID", "-c", "Name"], capture_output=True, text=True, check=True)

        for line in out.stdout.splitlines():
            instance_id, instance_name = line.split(None, 1)
            if name in instance_name:
                 delete_instance(instance_id)

        logger.error(f"{colors.RED}OpenStack server creation command failed: {e}{colors.RESET}\n\nFor more information about the error, please see the log: /var/log/nova/nova-compute.log")
        sys.exit(1) 

    finally:
        if os.path.exists(config_drive_file_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(config_drive_file_path)))
            shutil.rmtree(base_dir, ignore_errors=True)

def allocate_floating_ip(external_net: str = EXTERNAL_NET) -> str:
    """Allocate a floating IP and return its address."""
    print("Allocating floating IP ...")
    fip = _os_value("floating", "ip", "create", "-c", "floating_ip_address", external_net)
    if not fip:
        logger.error("Unable to allocate floating IP")
        sys.exit(1)
    return fip


def attach_floating_ip(server_id: str, fip: str) -> None:
    """Attach floating IP to server using server ID (not name)."""
    print(f"Attaching floating IP {fip} to instance {server_id} ...\n")
    _os("server", "add", "floating", "ip", server_id, fip)


def wait_for_active(server_id: str, timeout: int = 1000) -> None:
    """Poll server status by ID until ACTIVE or ERROR."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _os_value("server", "show", server_id, "-c", "status")
        if status == "ACTIVE":
            return
        if status == "ERROR":
            logger.error(f"Server {server_id} is in ERROR state")
            sys.exit(1)
        time.sleep(5)
    logger.warning(f"Server {server_id} not ACTIVE after {timeout}s")


def print_summary(name: str, fip: str, key_path: str | None, is_password: bool,
                  username: str, password: str, os_type: str, ip_address: str = None) -> None:

    os_type = (os_type or "").lower()
    ip = fip or ip_address

    print(f"{colors.GREEN}Instance '{name}' successfully started{colors.RESET}\n")

    if fip:
        print(f"Attached Floating IP : {fip}\n")

    if os_type == "linux":
        ssh_target = ip

        if key_path:
            ssh_cmd = f"ssh -i {key_path} {username}@{ssh_target}"
            print(f"You can connect to the instance with:\n  {ssh_cmd}\n")
        else:
            ssh_cmd = f"ssh {username}@{ssh_target}"
            print(f"You can connect to the instance with:\n  {ssh_cmd}\n")
            logger.info(f"{colors.YELLOW}Specify your private key with -i if password auth is disabled.{colors.RESET}\n")

    elif os_type == "windows":
        print(f"You can connect via RDP to: {ip}\n")

        logger.warning(
            f"{colors.YELLOW}Ensure that a security group rule is configured "
            f"to allow inbound TCP port 3389 (RDP) from your public IP or network."
            f"{colors.RESET}\n"
        )

    if is_password:
        print(
            f"You can log in with credentials:\n"
            f"  username: {username}\n"
            f"  password: {password}"
        )

def launch(
    name: str           = "cirros-instance",
    image: str          = DEFAULT_IMAGE,
    flavor: str         = DEFAULT_FLAVOR,
    network: str        = DEFAULT_NETWORK,
    keypair: str        = "",
    key_path: str       = SSH_KEY_PATH,
    external_net: str   = EXTERNAL_NET,
    password: str       = "",
    timeout: int        = 100
) -> None:

    prohibited_pw_chars = [' ', '$', '`', '\\']

    os.makedirs(SSH_KEY_PATH, exist_ok=True)
    key_path = os.path.join(SSH_KEY_PATH, f"id_{name}")

    #keypair = ensure_keypair(key_path, name)

    image_id   = get_default_image(image)
    flavor_id  = get_default_flavor(flavor)
    network_id = get_default_network(network)

    props = get_image_properties(image_id) or {}

    os_type      = (props.get("os_type") or "").lower()
    os_distro    = (props.get("os_distro") or "").lower()
    image_name   = (props.get("name") or "").lower()
    os_admin_user = (props.get("os_admin_user") or "")

    password_enabled = True

    fip: str = None
    instance_ip_address: str = None

    if " " in password:
        logger.error(f"{colors.RED}Cloud-init password invalid: contains spaces{colors.RESET}")
        sys.exit(1)
    elif any(c in password for c in prohibited_pw_chars):
        logger.error(f"{colors.RED}Cloud-init password invalid: illegal characters{colors.RESET}")
        sys.exit(1)

    if not keypair:
        key_path = key_path or os.path.join(SSH_KEY_PATH, f"id_{name}")
        keypair = ensure_keypair(key_path, name)
        with open(f"{key_path}.pub", "r") as f:
            public_key = f.read().strip()
    else:
        key_path = None
        public_key = None

    if "cirros" in image_name and password not in (None, ""):
        password_enabled = False
        logger.info(f"{colors.YELLOW}CirrOS detected. Skipping password configuration (unsupported image).{colors.RESET}\n")

    elif (not os_type or not os_distro) and password not in (None, ""):
        password_enabled = False
        logger.warning(f"{colors.YELLOW}Missing image metadata. Skipping password configuration for safety.{colors.RESET}\n")

    elif os_type not in ("windows", "linux") and password not in (None, ""):
        password_enabled = False
        logger.warning(
        f"{colors.YELLOW}Invalid ostype '{os_type}' specified. "
        f"Valid values are 'windows' or 'linux'. "
        f"No config drive will be created for this VM.{colors.RESET}\n"
    )

    if password_enabled and password:

        server_id = create_server_with_password(
            name, image_id, flavor_id, network_id,
            keypair, os_type, os_admin_user, password, public_key
        )
    else:
        server_id = create_server(
            name, image_id, flavor_id, network_id, keypair
        )

    wait_for_active(server_id, timeout)

    if network != EXTERNAL_NET:

        if internal_router_has_gateway():
            fip = allocate_floating_ip(external_net)

            attach_floating_ip(server_id, fip)
        else:
            instance_ip_address = get_instance_ip(name, network)

            logger.warning(
            f"{colors.YELLOW}The internal router does not have a gateway connected to the external network. "
            f"Floating IP creation will be skipped, and the '{network}' network will be directly associated "
            f"with the instance '{server_id}'.{colors.RESET}"
        )
    else:
        instance_ip_address = get_instance_ip(name, network)
    
    if password_enabled and password:
        print_summary(name, fip, key_path, True, os_admin_user, password, os_type, instance_ip_address)
    elif "cirros" in image_name:
        print_summary(name, fip, key_path, False, "cirros", None, "linux", instance_ip_address)
    else:
        print_summary(name, fip, key_path, False, os_admin_user, None, os_type, instance_ip_address)