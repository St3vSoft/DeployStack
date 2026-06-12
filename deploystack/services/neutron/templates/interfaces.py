from typing import List, Dict, Optional

def generate_interfaces_file(
    lines: List[str],
    bridges: Optional[List[Dict]] = None,
    mgmt_ifaces: Optional[List[Dict]] = None,
    loopback: bool = True
) -> None:


    if loopback and not any(l.startswith("auto lo") for l in lines):
        lines.extend([
            "auto lo",
            "iface lo inet loopback",
            ""
        ])

    if mgmt_ifaces:
        for iface in mgmt_ifaces:
            name = iface["name"]

            if any(l.startswith(f"auto {name}") for l in lines):
                continue

            lines.extend([
                f"auto {name}",
                f"iface {name} inet static",
                f"    address {iface['address']}",
                f"    netmask {iface['netmask']}",
                f"    gateway {iface['gateway']}",
                f"    dns-nameservers {iface['dns_servers']}",
                ""
            ])

    if bridges:
        for br in bridges:
            name = br["name"]
            ports = br.get("ports", [])

            if any(l.startswith(f"auto {name}") for l in lines):
                continue

            lines.append(f"auto {name}")
            lines.append(f"iface {name} inet manual")

            lines.append(f"    pre-up ovs-vsctl --may-exist add-br {name}")

            for port in ports:
                lines.append(f"    pre-up ovs-vsctl --may-exist add-port {name} {port}")
                lines.append(f"    pre-up ip link set {port} up")

            lines.append("")