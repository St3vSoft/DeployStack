
auto {iface}
iface {iface} inet manual
    pre-up ovs-vsctl --may-exist add-br {bridge}
    pre-up ovs-vsctl --may-exist add-port {bridge} {iface}
    up ip link set {iface} up
    down ip link set {iface} down

auto {bridge}
iface {bridge} inet static
    address {ip_address}
    netmask {ip_address_netmask}
    pre-up ovs-vsctl --may-exist add-br {bridge}
    pre-up ovs-vsctl --may-exist add-port {bridge} {iface}
    pre-up ip link set {iface} up