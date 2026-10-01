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

def create_share_types(default_type_shares, env):
    
    share_type_list = json.loads(os_run_output(["openstack", "share", "type", "list", "-f", "json"], env=env) or "[]")

    allowed_extra_specs = {
        "driver_handles_share_servers",
        "snapshot_support",
        "create_share_from_snapshot_support",
        "revert_to_snapshot_support",
        "mount_snapshot_support",
    }

    for share_type in default_type_shares:
        share_type_name = share_type["name"]
        is_share_public = parse_bool(
            share_type.get("is_public"),
            False
        )

        extra_specs = {}

        for extra_spec in share_type.get("extra_specs", []):
            for key, value in extra_spec.items():
                if key not in allowed_extra_specs:
                    continue

                extra_specs[key] = (
                    "True" if parse_bool(value, False) else "False"
                )

        if any(st.get("Name") == share_type_name for st in share_type_list):
            continue

        dhss = extra_specs.pop(
            "driver_handles_share_servers",
            "False"
        )

        cmd = ["openstack", "share", "type", "create", share_type_name, dhss]

        if is_share_public:
            cmd += ["--public", "true"]

        if extra_specs:
            cmd.append("--extra-specs")
            cmd.extend(
                f"{key}={value}"
                for key, value in extra_specs.items()
            )

        print()

        if not os_run(cmd, f"Creating '{share_type_name}' share type... ", env=env):
            return False

        share_type_list.append({"Name": share_type_name})

    return True

def create_shares(shares, env, dhss: bool = False):

    share_list = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env) or "[]")

    for share in shares:
        share_name = share["name"]
        share_type = share.get("share_type") or "default_share_type"
        share_protocol = share["share_protocol"]
        share_size = share["share_size"]
        is_public = parse_bool(share["is_public"], False)
        share_network = None

        if dhss:
            share_network = share["share_network"]

        existing_share = next((item for item in share_list if item.get("Name", item.get("name")) == share_name), None)

        if existing_share:
            print(f"{colors.YELLOW}{share_name} already exists, checking status...{colors.RESET}")
            
            share_id = existing_share.get("ID", existing_share.get("id"))
            status = existing_share.get("status", "").lower()

            if status == "error":
                if not os_run(["openstack", "share", "delete", share_id], f"Deleting failed '{share_id}' share...") : return False
        else:
            print()
            
            share_create_cmd = ["openstack", "share", "create", "--name", share_name, "--share-type", share_type]

            if dhss:
                share_create_cmd += ["--share-network", share_network]

            if is_public:
                share_create_cmd += ["--public", "true"]
            
            share_create_cmd += [share_protocol, str(share_size)]

            if not os_run(share_create_cmd, f"Creating share '{share_name}'... ", env=env): return False

            print()

            if dhss:
                share_info = wait_dhss_share_available(share_name, env)
            else:
                share_info = wait_share_available(share_name, env)

            if not share_info: return False

            share_id = share_info.get("id")

        if not share_id:
            print(f"\n{colors.RED}ERROR: Unable to retrieve {share_name} id{colors.RESET}")
            return False

        export_path = None

        for _ in range(10):
            share_info = json.loads(os_run_output(["openstack", "share", "show", share_id, "-f", "json"], env=env) or "{}")
            export_locations = share_info.get("export_locations", "")

            if export_locations:
                if isinstance(export_locations, str):
                    for line in export_locations.splitlines():
                        if line.strip().startswith("path ="):
                            export_path = line.split("=", 1)[1].strip()
                            break

                elif isinstance(export_locations, list):
                    first_location = export_locations[0]

                    if isinstance(first_location, dict):
                        export_path = first_location.get("path")
                    elif isinstance(first_location, str):
                        export_path = first_location

                if export_path:
                    break

            time.sleep(3)

        if not export_path:
            print(f"\n{colors.RED}ERROR: {share_name} has no export location available{colors.RESET}")
            return False
        
        print()

        for rule in share.get("access_rules", []):
            rule_access_type = rule["type"]
            rule_access = rule["access"]
            rule_access_level = rule["level"]

            access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")

            rule_exists = any(access.get("access_type", access.get("Access Type")) == rule_access_type and access.get("access_to", access.get("Access To")) == rule_access for access in access_list)

            if rule_exists:
                print(f"{colors.YELLOW}Access rule {rule_access} already exists, skipping creation.{colors.RESET}")
                continue

            if not os_run(["openstack", "share", "access", "create", "--access-level", rule_access_level, share_id, rule_access_type, rule_access], f"Adding access rule {rule_access} to '{share_name}'... ", env=env):
                return False

            for _ in range(10):
                access_list = json.loads(os_run_output(["openstack", "share", "access", "list", share_id, "-f", "json"], env=env) or "[]")

                if any(access.get("access_type", access.get("Access Type")) == rule_access_type and access.get("access_to", access.get("Access To")) == rule_access for access in access_list):
                    break

                time.sleep(2)
            else:
                print(f"\n{colors.RED}ERROR: access rule {rule_access} is not created{colors.RESET}")
                return False

    return True