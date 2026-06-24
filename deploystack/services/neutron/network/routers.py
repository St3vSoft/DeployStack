import json

from ....utils.core.commands import os_run, os_run_output
from ....utils.config.helpers import parse_bool
from ....utils.core import colors


def create_custom_network_router(
    routers_list: list,
    provider_networks: list,
    public_bridge: str,
    internal_flat_bridge: str,
    env
) -> bool:

    for pn in provider_networks:

        if pn.get("bridge") in (public_bridge, internal_flat_bridge, "br-int"):
            continue
        else:
            print()

        network_name = pn.get("name")
        subnet = pn.get("subnet", {}) or {}

        attach_external_router = parse_bool(
            subnet.get("attach_external_router", False)
        )

        if not attach_external_router:
            continue

        router_name = f"{network_name}_router"
        subnet_name = f"{network_name}_subnet"

        subnet_info_raw = os_run_output(
            ["openstack", "subnet", "list", "--name", subnet_name, "-f", "json"],
            env=env
        )
        subnet_list = json.loads(subnet_info_raw) if subnet_info_raw else []
        subnet_exists = len(subnet_list) > 0

        router_exists = any(
            r.get("Name") == router_name or r.get("name") == router_name
            for r in routers_list
        )

        if not router_exists:
            if not os_run(
                ["openstack", "router", "create", router_name],
                f"Creating router '{router_name}'...",
                env=env
            ):
                return False
        else:
            print(f"{colors.YELLOW}'{router_name}' already exists{colors.RESET}")

        router_data = json.loads(
            os_run_output(
                ["openstack", "router", "show", router_name, "-f", "json"],
                env=env
            )
        )

        has_gateway = bool(router_data.get("external_gateway_info"))

        if not has_gateway:
            if not os_run(
                [
                    "openstack", "router", "set",
                    router_name,
                    "--external-gateway", "public"
                ],
                f"Setting external gateway for '{router_name}'...",
                env=env
            ):
                return False

        if subnet_exists:
            subnet_id = subnet_list[0].get("ID") or subnet_list[0].get("id")

            ports_raw = os_run_output(
                [
                    "openstack", "port", "list",
                    "--router", router_name,
                    "-f", "json"
                ],
                env=env
            )
            ports = json.loads(ports_raw) if ports_raw else []

            already_attached = any(
                subnet_id in [
                    fip.get("subnet_id")
                    for fip in (p.get("Fixed IP Addresses") or p.get("fixed_ips") or [])
                ]
                for p in ports
            )

            if not already_attached:
                if not os_run(
                    [
                        "openstack", "router", "add",
                        "subnet", router_name, subnet_name
                    ],
                    f"Adding '{subnet_name}' subnet to router...",
                    env=env
                ):
                    return False
            else:
                print(
                    f"{colors.YELLOW}'{subnet_name}' already attached to '{router_name}'{colors.RESET}"
                )

    return True