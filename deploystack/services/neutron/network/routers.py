import json

from ....utils.core.commands import os_run, os_run_output, run_command
from ....utils.config.helpers import parse_bool

from ....utils.core import colors

def create_custom_network_router(
    subnets_list: list,
    routers_list: list,
    provider_networks: list,
    public_bridge: str,
    env
) -> bool:

    for pn in provider_networks:

        if pn.get("bridge") in (public_bridge, "br-int"):
            continue

        network_name = pn.get("name")
        subnet = pn.get("subnet", {}) or {}

        attach_external_router = parse_bool(
            subnet.get("attach_external_router", False)
        )

        if not attach_external_router:
            continue

        router_name = f"{network_name}_router"
        subnet_name = f"{network_name}_subnet"

        router_exists = any(
            r.get("Name") == router_name or r.get("name") == router_name
            for r in routers_list
        )

        subnet_exists = any(
            (s.get("Name") or s.get("name")) == subnet_name
            for s in subnets_list
        )

        # 1. CREATE ROUTER
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
            subnet_os = json.loads(
                os_run_output([
                    "openstack", "subnet", "show",
                    subnet_name,
                    "-f", "json"
                ], env=env)
            )

            subnet_id = subnet_os["id"]

            router_ifaces = json.loads(
                os_run_output([
                    "openstack", "router", "show",
                    router_name,
                    "-f", "json"
                ], env=env)
            )

            interfaces = router_ifaces.get("interfaces_info") or []

            already_attached = any(
                i.get("subnet_id") == subnet_id
                for i in interfaces
            )

            if not already_attached:
                if not run_command(
                    [
                        "openstack", "router", "add",
                        "subnet", router_name, subnet_name
                    ],
                    f"Adding '{subnet_name}' subnet to router...",
                    env=env
                ):
                    return False

    return True