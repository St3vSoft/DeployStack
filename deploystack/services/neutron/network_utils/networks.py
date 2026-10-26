import json
import ipaddress

from ....utils.core.commands import run_command, run_command_output, run_command_sync
from ....utils.config.helpers import parse_bool

from ....utils.config.parser import get
from ....utils.core.system_utils import iface_exists

from ....utils.core import colors

from ..templates import INTERFACE_BRIDGE_TEMPLATE

def _subnet_overlaps(cidr: str, env) -> bool:
    out = run_command_output(["openstack", "subnet", "list", "-f", "json"], False, env=env)
    subnets = json.loads(out)

    for s in subnets:
        existing_cidr = s.get("Subnet") or s.get("CIDR") or s.get("cidr")

        if not existing_cidr:
            continue

        if ipaddress.ip_network(cidr).overlaps(ipaddress.ip_network(existing_cidr)):
            return True

    return False

def append_custom_bridges_ifaces_config(config, bridges: list, bridges_interfaces_content: str) -> str:

    with open(INTERFACE_BRIDGE_TEMPLATE, "r") as f:
        template = f.read()

    networks = get(config, "neutron.provider_networks", default=[])
    blocks = []

    for b in bridges:
        port, bridge = b.get("port"), b.get("name")
        if not port or not bridge:
            continue

        network = next((n for n in networks if n.get("bridge") == bridge), None)
        if not network:
            continue

        subnet = get(network, "subnet", default={})
        cidr, gateway = subnet.get("cidr"), subnet.get("gateway")
        if not cidr or not gateway:
            continue

        dhcp_start = get(subnet, "range.start")
        dhcp_end = get(subnet, "range.end")

        if get(subnet, "allow_dhcp", False) and dhcp_start and dhcp_end:
            ip = ipaddress.ip_address(dhcp_start) - 1
        else:
            ip = ipaddress.ip_address(gateway) + 1

        netmask = str(ipaddress.ip_network(cidr, strict=False).netmask)

        blocks.append(template.format(
            iface=port,
            bridge=bridge,
            ip_address=str(ip),
            ip_address_netmask=netmask,
        ))

    if blocks:
        bridges_interfaces_content += "\n" + "\n".join(blocks)

    return bridges_interfaces_content

def bring_up_custom_bridges_ifaces(bridges: list):
    for b in bridges:

        iface = b.get("port")
        bridge = b.get("name")

        if not run_command(["ip", "link", "set", iface, "up"], f"Bringing {iface} up"):
            return False
        if not run_command(["ip", "link", "set", bridge, "up"], f"Bringing {bridge} up"):
            return False
            
    return True

def add_custom_bridges(bridges: list, public_bridge: str, internal_flat_bridge: str, tunnel_bridge: str):

    for b in bridges:
        port = b.get("port")
        bridge = b.get("name")

        if bridge in (public_bridge, tunnel_bridge, "br-int", internal_flat_bridge):
            continue
        else:
            print()

        if not bridge or not port:
            continue

        if not run_command(["ovs-vsctl", "--may-exist", "add-br", bridge, "--", "--may-exist", "add-port", bridge, port], f"Adding bridge {bridge} with {port} port"): return False

    return True

def clean_custom_bridges(bridges: list, public_bridge: str, internal_flat_bridge: str, tunnel_bridge: str):

    print("[DEBUG] === START clean_custom_bridges ===", flush=True)
    print(f"[DEBUG] Bridges ricevuti: {bridges}", flush=True)
    print(f"[DEBUG] public_bridge={public_bridge}, internal_flat_bridge={internal_flat_bridge}, tunnel_bridge={tunnel_bridge}", flush=True)

    for i, b in enumerate(bridges):
        print(f"\n[DEBUG] --- Bridge {i + 1}/{len(bridges)} ---", flush=True)

        bridge = b.get("name")
        port = b.get("port")

        print(f"[DEBUG] name={bridge!r}, port={port!r}", flush=True)

        if bridge in (public_bridge, tunnel_bridge, "br-int", internal_flat_bridge):
            print(f"[DEBUG] SKIP: bridge escluso ({bridge})", flush=True)
            continue

        if not bridge or not port:
            print(f"[DEBUG] SKIP: bridge o port mancante (bridge={bridge!r}, port={port!r})", flush=True)
            continue

        print(f"[DEBUG] Verifica iface_exists({bridge!r})...", flush=True)

        try:
            exists = iface_exists(bridge)
            print(f"[DEBUG] iface_exists({bridge!r}) -> {exists}", flush=True)
        except Exception as e:
            print(f"[ERROR] Eccezione in iface_exists({bridge!r}): {type(e).__name__}: {e}", flush=True)
            raise

        if not exists:
            print(f"[DEBUG] SKIP: interfaccia {bridge} non esistente", flush=True)
            continue

        print(f"[DEBUG] Flush IP su {port}...", flush=True)
        try:
            result = run_command(
                ["ip", "addr", "flush", "dev", port],
                f"Flushing IPs on {port}",
                ignore_errors=True
            )
            print(f"[DEBUG] Risultato flush IP: {result!r}", flush=True)
        except Exception as e:
            print(f"[ERROR] Eccezione durante flush IP: {type(e).__name__}: {e}", flush=True)
            raise

        print(f"[DEBUG] Disattivazione interfaccia {port}...", flush=True)
        try:
            result = run_command(
                ["ip", "link", "set", port, "down"],
                f"Bringing {port} down",
                ignore_errors=True
            )
            print(f"[DEBUG] Risultato link down: {result!r}", flush=True)
        except Exception as e:
            print(f"[ERROR] Eccezione durante link down: {type(e).__name__}: {e}", flush=True)
            raise

        cmd = ["ovs-vsctl", "--if-exists", "del-port", bridge, port]
        print(f"[DEBUG] Esecuzione: {cmd!r}", flush=True)

        try:
            result = run_command_sync(cmd)
            print(f"[DEBUG] Risultato del-port: {result!r}", flush=True)
        except Exception as e:
            print(f"[ERROR] Eccezione in del-port: {type(e).__name__}: {e}", flush=True)
            raise

        if not result:
            print(f"[ERROR] del-port fallito: bridge={bridge}, port={port}", flush=True)
            return False

        cmd = ["ovs-vsctl", "--if-exists", "del-br", bridge]
        print(f"[DEBUG] Esecuzione: {cmd!r}", flush=True)

        try:
            result = run_command_sync(cmd)
            print(f"[DEBUG] Risultato del-br: {result!r}", flush=True)
        except Exception as e:
            print(f"[ERROR] Eccezione in del-br: {type(e).__name__}: {e}", flush=True)
            raise

        if not result:
            print(f"[ERROR] del-br fallito: bridge={bridge}", flush=True)
            return False

        print(f"[DEBUG] Bridge {bridge} eliminato correttamente", flush=True)

    print("[DEBUG] === END clean_custom_bridges: return True ===", flush=True)
    return True

def create_custom_networks(
    networks_list: list,
    provider_networks: list, 
    public_bridge: str,
    tenant_bridge: str,
    tunnel_bridge: str,
    env):

    for pn in provider_networks:

        bridge = pn.get("bridge")
        physnet = pn.get("physnet")
        net_type = pn.get("type")

        if net_type != "local" and bridge in (public_bridge, tunnel_bridge, "br-int", tenant_bridge):
            continue
        else:
            print()
    
        network_name = pn.get("name")

        subnet = pn.get("subnet", {})

        vlan_range = pn.get("vlan_range")

        allow_dhcp  = parse_bool(subnet.get("allow_dhcp", False))
        is_external = parse_bool(subnet.get("is_external", False))

        subnet_cidr = subnet.get("cidr")
        subnet_range_start = subnet.get("range", {}).get("start")
        subnet_range_end = subnet.get("range", {}).get("end")
        subnet_gateway = subnet.get("gateway")

        subnet_dns = subnet.get("dns") or []

        network_cmd = []

        subnet_name = f"{network_name}_subnet"

        network_exists = any((net.get("Name") or net.get("name")) == network_name for net in networks_list)
        physnet_name = physnet or network_name

        if net_type == "flat":

            network_cmd = [
                "openstack", "network", "create",
                "--share",
                "--provider-physical-network", physnet_name,
                "--provider-network-type", "flat"
            ]

        elif net_type == "vlan":
            if not vlan_range:
                continue

            start, _ = map(int, vlan_range.split(":"))
            vlan_id = start

            network_cmd = [
                "openstack", "network", "create",
                "--share",
                "--provider-physical-network", network_name,
                "--provider-network-type", "vlan",
                "--provider-segment", str(vlan_id),
            ]
        elif net_type == "local":
            network_cmd = [
                "openstack", "network", "create",
                "--share",
                "--provider-network-type", "local"
            ]

        else:
            continue 

        if is_external:
            network_cmd.append("--external")

        network_cmd.append(network_name)

        if not network_exists:
            if not run_command(network_cmd, f"Creating '{network_name}' network...", env=env) : return False
        else:
            print(f"{colors.YELLOW}'{network_name}' network already exists, skipping creation.{colors.RESET}")

        if subnet_cidr:

            subnet_cmd = [
                "openstack", "subnet", "create",
                "--network", network_name,
                "--subnet-range", subnet_cidr
            ]
    
            if subnet_gateway is not None:
                subnet_gateway = str(subnet_gateway).strip()

            if subnet_gateway:
                subnet_cmd += ["--gateway", subnet_gateway]
            else:
                subnet_cmd += ["--gateway", "none"]

            if allow_dhcp:
                subnet_cmd.append("--dhcp")
            else:
                subnet_cmd.append("--no-dhcp")

            for dns in subnet_dns:
                subnet_cmd += ["--dns-nameserver", dns]

            if subnet_range_start is not None and subnet_range_end is not None:
                subnet_cmd += ["--allocation-pool", f"start={subnet_range_start},end={subnet_range_end}"]

            subnet_cmd.append(subnet_name)

            if not _subnet_overlaps(cidr=subnet_cidr, env=env):
                if not run_command(subnet_cmd, f"Creating '{network_name}' network subnet...", env=env) : return False
            else:
                print(f"{colors.YELLOW}'{network_name}' network subnet already exists, skipping creation.{colors.RESET}")
        
    return True