import json

from ....utils.core.commands import os_run, os_run_output
from ....utils.config.helpers import parse_bool
from ....utils.core import colors

def safe_json(cmd, env):
    out = os_run_output(cmd, env=env)
    return json.loads(out) if out else {}

def router_exists(router_name, env):
    data = safe_json(
        ["openstack", "router", "list", "-f", "json"],
        env
    )

    return any(r.get("Name") == router_name for r in data)

def has_gateway(router_name, env):
    data = safe_json(
        ["openstack", "router", "show", router_name, "-f", "json"],
        env
    )

    return bool(data.get("external_gateway_info"))

def is_subnet_attached(router_name, subnet_id, env):

    ports = safe_json(
        ["openstack", "port", "list", "--router", router_name, "-f", "json"],
        env
    )

    for p in ports:
        fixed_ips = p.get("fixed_ips") or p.get("Fixed IP Addresses") or []

        for ip in fixed_ips:
            if isinstance(ip, dict) and ip.get("subnet_id") == subnet_id:
                return True

    return False

def create_custom_network_router(
    routers_list,
    provider_networks,
    public_bridge,
    tenant_bridge,
    tunnel_bridge,
    env
) -> bool:

    internal_bridges = {
        public_bridge,
        tenant_bridge,
        tunnel_bridge,
        "br-int"
    }

    for pn in provider_networks:

        subnet_cfg = pn.get("subnet") or {}

        if not parse_bool(subnet_cfg.get("attach_external_router", False)):
            continue

        bridge = pn.get("bridge")

        if bridge in internal_bridges:
            continue

        network_name = pn.get("name")
        router_name = f"{network_name}_router"
        subnet_name = f"{network_name}_subnet"

        if not router_exists(router_name, env):
            if not os_run(
                ["openstack", "router", "create", router_name],
                f"Creating router {router_name}...",
                env=env
            ):
                return False

        if not has_gateway(router_name, env):
            if not os_run(
                ["openstack", "router", "set", router_name,
                 "--external-gateway", "public"],
                f"Setting external gateway for {router_name}...",
                env=env
            ):
                return False

        subnet_list = safe_json(
            ["openstack", "subnet", "list", "--name", subnet_name, "-f", "json"],
            env
        )

        if not subnet_list:
            print(f"Subnet {subnet_name} not found, skipping attach")
            continue

        subnet_id = subnet_list[0].get("ID") or subnet_list[0].get("id")

        if not is_subnet_attached(router_name, subnet_id, env):

            if not os_run(
                ["openstack", "router", "add", "subnet",
                 router_name, subnet_name],
                f"Attaching {subnet_name} to {router_name}...",
                env=env
            ):
                return False

    return True