import json

from ....utils.core.commands import os_run, os_run_output
from ....utils.config.helpers import parse_bool

from ....utils.core import colors

def create_custom_network_router(
        subnets_list: list,
        routers_list: list,
        provider_networks: list,
        public_bridge: str,
        env
):
     
    for pn in provider_networks:
                
        if pn.get("bridge") in (public_bridge, "br-int"):
            continue

        network_name = pn.get("name")

        subnet = pn.get("subnet", {})
        attach_external_router = parse_bool(subnet.get("attach_external_router", False))

        if not attach_external_router:
            continue

        router_name = f"{network_name}_router"
        subnet_name = f"{network_name}_subnet"

        router_exists = any(r.get("Name") == router_name for r in routers_list)
        subnet_exists = any(
            (sub.get("Name") or sub.get("name")) == subnet_name
            for sub in subnets_list
        )

        if not router_exists:
            if not os_run(["openstack", "router", "create", router_name], f"Creating '{router_name}' router...", env=env):
                return False
        else:
            print(f"{colors.YELLOW}'{router_name}' Router already exists, skipping creation.{colors.RESET}")

        external_gateways_list = json.loads(os_run_output(["openstack", "router", "show", router_name, "-f", "json", "-c", "external_gateways"], env=env))
        interfaces_info_list = json.loads(os_run_output(["openstack", "router", "show", router_name, "-f", "json", "-c", "interfaces_info"], env=env))

        if not external_gateways_list.get("external_gateways"):
            if not os_run (
                ["openstack", "router", "set", router_name, "--external-gateway", "public"],
                f"Setting external gateway for {router_name} router...", env=env
            ):
                return False

        if not interfaces_info_list.get("interfaces_info"):
            if not os_run(
                ["openstack", "router", "add", "subnet", router_name, subnet_name],
                f"Adding '{subnet_name}' subnet to router...", env=env
            ):
                return False
        
        return True