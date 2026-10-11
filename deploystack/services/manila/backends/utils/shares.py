import json
import time

from .....utils.core.commands import os_run_output, os_run
from ..utils import wait_share_available, wait_dhss_share_available

from .....utils.config.helpers import parse_bool
from .....utils.core import colors

SUPPORTED_EXTRA_SPECS = {
    "driver_handles_share_servers",
    "snapshot_support",
    "create_share_from_snapshot_support",
    "revert_to_snapshot_support",
    "mount_snapshot_support",
}

def _get_share_network_id(share_network_name, env):

    share_networks = json.loads(os_run_output(["openstack", "share", "network", "list", "-f", "json"], env=env) or "[]")

    share_network = next((item for item in share_networks if item.get("Name", item.get("name")) == share_network_name), None)

    if not share_network:
        return None

    return share_network.get("ID", share_network.get("id"))

def _get_share_server_for_share(share_id, env):

    result = os_run_output(["openstack", "share", "show", share_id, "-f", "json"], env=env)

    if not result:
        return None

    try:
        share = json.loads(result)
    except json.JSONDecodeError:
        return None

    return share.get("share_server_id") or share.get("Share Server ID")

def _get_server_for_share_server(share_server_id, env):

    result = os_run_output(["openstack", "server", "list", "--all-projects", "-f", "json"], env=env)

    if not result:
        return None

    try:
        servers = json.loads(result)
    except json.JSONDecodeError:
        return None

    expected_name = f"generic_{share_server_id}"

    for server in servers:
        name = server.get("Name", server.get("name"))

        if name == expected_name:
            return server.get("ID", server.get("id"))

    return None

def _wait_server_deleted(share_server_id, env, attempts=10, delay=3):

    for _ in range(attempts):
        server_id = _get_server_for_share_server(share_server_id, env)

        if not server_id:
            return True

        time.sleep(delay)

    return False

def _wait_share_deleted(share_id, env, attempts=10, delay=3):

    for _ in range(attempts):

        shares = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env,) or "[]")

        if not any(item.get("ID", item.get("id")) == share_id for item in shares): return True

        time.sleep(delay)

    print(f"{colors.RED}Share '{share_id}' was not removed within the expected time.{colors.RESET}")

    return False

def create_share_types(default_type_shares, env):
    
    share_type_list = json.loads(os_run_output(["openstack", "share", "type", "list", "-f", "json"], env=env) or "[]")

    for share_type in default_type_shares:

        share_type_name = share_type["name"]

        is_share_public = parse_bool(share_type.get("is_public"), False)

        extra_specs = {}

        for extra_spec in share_type.get("extra_specs", []):
            for key, value in extra_spec.items():
                if key not in SUPPORTED_EXTRA_SPECS:
                    continue

                extra_specs[key] = ("True" if parse_bool(value, False) else "False")

        if any(st.get("Name") == share_type_name for st in share_type_list):
            continue

        dhss = extra_specs.pop("driver_handles_share_servers", "False")

        cmd = ["openstack", "share", "type", "create", share_type_name, dhss]

        if is_share_public:
            cmd += ["--public", "true"]

        if extra_specs:
            cmd.append("--extra-specs")
            cmd.extend(f"{key}={value}" for key, value in extra_specs.items())

        print()

        if not os_run(cmd, f"Creating '{share_type_name}' share type... ", env=env): return False

        share_type_list.append({"Name": share_type_name})

    return True

def create_shares(shares, env, dhss=False):

    share_list = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env) or "[]")

    for share in shares:
        name, protocol, size = share["name"], share["share_protocol"], share["share_size"]
        share_type = share.get("share_type") or "default_share_type"
        is_public = parse_bool(share.get("is_public"), False)
        share_network = None

        if dhss:
            share_network = _get_share_network_id(share["share_network"], env)
            if not share_network:
                print(f"{colors.RED}Share network '{share['share_network']}' not found.{colors.RESET}")
                return False

        existing = next((s for s in share_list if s.get("Name", s.get("name")) == name), None)
        share_id = None

        if existing:
            share_id = existing.get("ID", existing.get("id"))
            status = existing.get("Status", existing.get("status", "")).lower()

            if not share_id:
                print(f"{colors.RED}Could not determine share ID.{colors.RESET}")
                return False

            if status == "available":
                continue
            if status not in ("error", "error_deleting"):
                print(f"{colors.YELLOW}Share '{name}' is in status '{status}', skipping.{colors.RESET}")
                continue

            share_server_id = _get_share_server_for_share(share_id, env) if dhss else None

            if not os_run(["openstack", "share", "delete", share_id], f"Deleting failed '{name}' share...", env=env):
                return False
            if not _wait_share_deleted(share_id, env):
                return False

            if dhss and share_server_id:
                if not os_run(["openstack", "share", "server", "delete", share_server_id], f"Deleting share server '{share_server_id}'...", env=env):
                    return False

                orphan_id = _get_server_for_share_server(share_server_id, env)
                if orphan_id:
                    if not os_run(["openstack", "server", "delete", orphan_id], f"Deleting orphaned Nova instance '{orphan_id}'...", env=env):
                        return False
                    if not _wait_server_deleted(share_server_id, env):
                        return False

            share_id = None

        if not share_id:
            cmd = ["openstack", "share", "create", "--name", name, "--share-type", share_type]

            if dhss:
                cmd += ["--share-network", share_network]
            if is_public:
                cmd += ["--public", "true"]

            cmd += [protocol, str(size)]

            if not os_run(cmd, f"Creating share '{name}'...", env=env):
                return False

            info = wait_dhss_share_available(name, env) if dhss else wait_share_available(name, env)

            if not info:
                return False
            
            share_id = info.get("id")

        if not share_id:
            print(f"{colors.RED}ERROR: Unable to retrieve {name} id{colors.RESET}")
            return False

        export_path = None
        for _ in range(10):
            info = json.loads(os_run_output(["openstack", "share", "show", share_id, "-f", "json"], env=env) or "{}")
            locations = info.get("export_locations", "")
            if isinstance(locations, str):
                export_path = next((line.split("=", 1)[1].strip() for line in locations.splitlines() if line.strip().startswith("path =")), None)
            elif isinstance(locations, list) and locations:
                first = locations[0]
                export_path = first.get("path") if isinstance(first, dict) else first if isinstance(first, str) else None
            if export_path:
                break
            time.sleep(3)

        if not export_path:
            print(f"{colors.RED}ERROR: {name} has no export location available{colors.RESET}")
            return False

        for rule in share.get("access_rules", []):
            rule_type, access, level = rule["type"], rule["access"], rule["level"]
            access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")

            if any(a.get("access_type", a.get("Access Type")) == rule_type and a.get("access_to", a.get("Access To")) == access for a in access_list):
                print(f"{colors.YELLOW}Access rule {access} already exists, skipping.{colors.RESET}")
                continue

            if not os_run(["openstack", "share", "access", "create", "--access-level", level, share_id, rule_type, access], f"Adding access rule {access} to '{name}'...", env=env):
                return False

            for _ in range(10):
                access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")
                if any(a.get("access_type", a.get("Access Type")) == rule_type and a.get("access_to", a.get("Access To")) == access for a in access_list):
                    break
                time.sleep(2)
            else:
                print(f"{colors.RED}ERROR: access rule {access} was not created.{colors.RESET}")
                return False

    return True