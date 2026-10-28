from ....utils.core.commands import run_command, run_command_sync

from ....utils.config.parser import get
from ....utils.core.system_utils import iface_exists

from ..templates import INTERFACE_BRIDGE_TEMPLATE

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

    for b in bridges:
        bridge = b.get("name")
        port = b.get("port")

        if bridge in (public_bridge, tunnel_bridge, "br-int", internal_flat_bridge):
            continue

        if not bridge or not port:
            continue

        if iface_exists(bridge):

            print()

            run_command(["ip", "addr", "flush", "dev", port],
                        f"Flushing IPs on {port}", ignore_errors=True)

            run_command(["ip", "link", "set", port, "down"],
                        f"Bringing {port} down", ignore_errors=True)

            if not run_command_sync(["ovs-vsctl", "--if-exists", "del-port", bridge, port]) : return False
            if not run_command_sync(["ovs-vsctl", "--if-exists", "del-br", bridge]) : return False

    return True
