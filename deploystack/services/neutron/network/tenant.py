import ipaddress
import json

from ....utils.core.commands import os_run, os_run_output
from ....utils.config.parser import get
from ....utils.core import colors
 
OVERLAY_TYPES = ("geneve", "vxlan")
VALID_TENANT_TYPES = ("geneve", "vxlan", "vlan", "flat")

def get_tenant_types(config, default="geneve"):

    types = get(config, "neutron.tenant_networks.TYPES", None)

    if not types:
        legacy = get(config, "neutron.tenant_network.TYPE", None)
        types = [legacy] if legacy else [default]

    if isinstance(types, str):
        types = [t.strip() for t in types.split(",") if t.strip()]

    result = []

    for t in types:
        t = str(t).lower()
        if t not in result:
            result.append(t)

    return result

def get_vlan_ranges(config):
    return get(config, "neutron.tenant_network.VLAN_RANGES", []) or []

def get_tenant_networks(config, legacy_type):

    networks = get(config, "neutron.tenant_network.networks", None)

    if networks is None:
        return [{
            "name": "internal",
            "type": legacy_type,
            "subnet_cidr": "10.0.0.0/24",
            "gateway": "10.0.0.1",
            "allocation_pool": {"start": "10.0.0.10", "end": "10.0.0.200"},
            "dns_servers": ["8.8.8.8"],
            "enable_dhcp": True,
            "router": "internal_router",
        }]
 
    return networks

def build_type_drivers(tenant_types):
    drivers = ["flat", "vlan", "local"]
    for t in tenant_types:
        if t not in drivers:
            drivers.append(t)
    return ",".join(drivers)

def build_bridge_mappings(config):

    mappings = {}

    for n in get(config, "neutron.provider_networks", []):
        if n.get("type") == "local" or not n.get("bridge"):
            continue

        mappings[n.get("physnet") or n["name"]] = n["bridge"]

    for v in get_vlan_ranges(config):
        if v.get("bridge"):
            mappings.setdefault(v["physnet"], v["bridge"])

    return ",".join(f"{physnet}:{bridge}" for physnet, bridge in mappings.items())

def build_network_vlan_ranges(config):
    entries = []

    for n in get(config, "neutron.provider_networks", []):
        if n.get("type") == "vlan":
            physnet = n.get("physnet") or n["name"]
            entries.append(f'{physnet}:{n["vlan_range"]}' if n.get["vlan_range"] else physnet)
    for v in get_vlan_ranges(config):
        entries.append(f'{v["physnet"]}:{v["range"]}')

    return ",".join(entries)

def merge_tenant_bridges(config, bridges):

    merged = list(bridges or [])
    known = {b.get("name") for b in merged}

    for v in get_vlan_ranges(config):
        name, port = v.get("bridge"), v.get("port")
        if name and port not in known:
            merged.append({"name": name, "port": port})
            known.add(name)

    return merged

def _provider_args(net):
    net_type = net["type"]

    if net_type in OVERLAY_TYPES:
        return ["--provider-network-type", net_type]

    args = ["--provider-network-type", net_type, "--provider-physical-network", net["physnet"]]

    if net_type == "vlan" and net.get("segmentation_id") is not None:
        args += ["--provider-segment", str(net["segmentation_id"])]

    return args

def _ensure_router(router, subnet_name, public_network_name, env):

    gateways = json.loads(os_run_output(["openstack", "router", "show", router, "-f", "json", "-c", "external_gateways"], env=env))

    if not gateways.get("external_gateways"):
        if not os_run(["openstack", "router", "set", router, "--external-gateway", public_network_name], f"Setting external gateway for router '{router}'...", env=env) : return False

    subnet_id = os_run_output(["openstack", "subnet", "show", subnet_name, "-f", "value", "-c", "id"], env=env)
    subnet_id = subnet_id.strip()

    interfaces = json.loads(os_run_output(["openstack", "router", "show", router, "-f", "json", "-c", "interfaces_info"], env=env))

    attached = {i.get("subnet_id") for i in (interfaces.get("interfaces_info") or [])}

    if subnet_id not in attached:
        if not os_run(["openstack", "router", "add", "subnet", router, subnet_name], f"Adding subnet '{subnet_name}' to router '{router}'...", env=env): return False

    return True

def create_tenant_networks(config, networks_list, subnets_list, routers_list, public_network_name, connect_routers, env, legacy_type="geneve"):

    tenant_networks = get_tenant_networks(config, legacy_type)

    if not tenant_networks:
        return True

    existing_networks = {n.get("Name") for n in networks_list}
    existing_subnets = {n.get("Name") for n in subnets_list}
    existing_routers = {n.get("Name") for n in routers_list}

    for net in tenant_networks:
        name = net["name"]
        subnet_name = f"{name}_subnet"

        print()

        if name in existing_networks:
            print(f"{colors.YELLOW}Network '{name}' already exists, skipping creation.{colors.RESET}")
        else:
            cmd = ["openstack", "network", "create"]
            if net.get("shared", True):
                cmd.append("--share")
            cmd += _provider_args(net) + [name]

            if not os_run(cmd, f"Creating tenant network '{name}' ({net['type']})...", env=env) : return False

            existing_networks.add(name)

        if subnet_name in existing_subnets:
            print(f"{colors.YELLOW}Subnet '{subnet_name}' already exists, skipping creation.{colors.RESET}")
        else:
            cmd = ["openstack", "subnet", "create", "--network", name, "--subnet-range", net["subnet_cidr"]]

            if net.get("gateway"):
                cmd += ["--gateway", net["gateway"]]

            pool = net.get("allocation_pool")
            if pool:
                cmd += ["--allocation-pool", f'start={pool["start"]},end={pool["end"]}']

            cmd.append("--dhcp" if net.get("enable_dhcp", True) else "--no-dhcp")

            for dns in net.get("dns_servers", []) or []:
                cmd += ["--dns-nameservers", dns]

            cmd.append(subnet_name)

        router = net.get("router")

        if not router:
            continue

        if router not in existing_routers:
            if not os_run(["openstack", "router", "create", router], f"Creating router '{router}'...", env=env): return False
            existing_routers.add(router)

        if connect_routers:
            if not _ensure_router(router, subnet_name, public_network_name, env): return False

    return True