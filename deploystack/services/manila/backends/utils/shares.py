import json
import time

from .....utils.core.commands import run_command, os_run_output, os_run
from ..utils import wait_share_available, wait_dhss_share_available

from .....utils.config.helpers import parse_bool
from .....utils.core import colors

def create_share_types(default_type_shares, env):

    share_type_list = json.loads(
        os_run_output(
            ["openstack", "share", "type", "list", "-f", "json"],
            env=env
        ) or "[]"
    )

    for share_type in default_type_shares:
        share_type_name = share_type["name"]
        is_share_public = parse_bool(share_type["is_public"], False)

        extra_specs = {}
        driver_handles_share_servers = None

        for extra_spec in share_type.get("extra_specs", []):
            if "driver_handles_share_servers" in extra_spec:
                driver_handles_share_servers = (
                    "True"
                    if parse_bool(extra_spec.get("driver_handles_share_servers"), False)
                    else "False"
                )

            for key in [
                "snapshot_support",
                "create_share_from_snapshot_support",
                "revert_to_share_snapshot_support",
                "mount_snapshot_support",
            ]:
                if parse_bool(extra_spec.get(key), False):
                    extra_specs[key] = "True"

        share_type_exists = any(
            st.get("Name") == share_type_name
            for st in share_type_list
        )

        if not share_type_exists:
            if driver_handles_share_servers is None:
                driver_handles_share_servers = "False"

            share_create_cmd = [
                "openstack",
                "share",
                "type",
                "create",
                share_type_name,
                driver_handles_share_servers,
            ]

            if is_share_public:
                share_create_cmd += ["--public", "True"]

            if extra_specs:
                share_create_cmd.append("--extra-specs")

                for key, value in extra_specs.items():
                    share_create_cmd.append(f"{key}={value}")

            if not os_run(
                share_create_cmd,
                f"Creating '{share_type_name}' share type...",
                env=env
            ):
                return False

            share_type_list.append({"Name": share_type_name})

    return True

def create_shares(shares, env, service_network_name: str, dhss: bool = False):

    share_list = json.loads(os_run_output(["openstack", "share", "list", "-f", "json"], env=env) or "[]")

    for share in shares:
            share_name = share["name"]
            share_type = share.get("share_type")
            share_protocol = share["share_protocol"]
            share_size = share["share_size"]
    
            existing_share = next((item for item in share_list if item.get("Name", item.get("name")) == share_name), None)
    
            if existing_share:
                print(f"{colors.YELLOW}{share_name} already exists, checking status...{colors.RESET}")
                share_id = existing_share.get("ID", existing_share.get("id"))
            else:
                share_create_cmd = ["openstack", "share", "create", "--name", share_name, "--share-type", share_type]

                if dhss:
                    share_create_cmd += ["--share-network", service_network_name]
                
                share_create_cmd += [share_protocol, str(share_size)]

                if not os_run(share_create_cmd, f"Creating share '{share_name}'...", env=env):
                    return False

                if dhss:
                    share_info = wait_dhss_share_available(share_name, env)
                else:
                    share_info = wait_share_available(share_name, env)
    
                if not share_info:
                    return False
    
                share_id = share_info.get("id")
    
            if not share_id:
                print(f"\n{colors.RED}ERROR: unable to retrieve {share_name} id{colors.RESET}")
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
    
                if not os_run(["openstack", "share", "access", "create", "--access-level", rule_access_level, share_id, rule_access_type, rule_access], f"Adding access rule {rule_access} to '{share_name}'...", env=env):
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