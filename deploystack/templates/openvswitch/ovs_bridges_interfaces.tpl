auto lo
iface lo inet loopback

auto {public_iface}
iface {public_iface} inet manual
    pre-up ovs-vsctl --may-exist add-br {public_bridge}
    pre-up ovs-vsctl --may-exist add-port {public_bridge} {public_iface}
    up ip link set {public_iface} up
    down ip link set {public_iface} down

auto {public_bridge}
iface {public_bridge} inet static
    address {ip_address}
    netmask {ip_address_netmask}
    gateway {subnet_address_gateway}
    dns-nameservers {subnet_address_dns_servers}
    pre-up ovs-vsctl --may-exist add-br {public_bridge}
    pre-up ovs-vsctl --may-exist add-port {public_bridge} {public_iface}
    pre-up ip link set {public_iface} up
    post-down ovs-vsctl --if-exists del-br {public_bridge}

# IF_INTERNAL_BRIDGE_BEGIN
auto {internal_bridge}
iface {internal_bridge} inet manual
    pre-up ovs-vsctl --may-exist add-br {internal_bridge}
    up ip link set {internal_bridge} up
# IF_INTERNAL_BRIDGE_END