from .helpers import get_provider_networks, interface_exists, validate_ip, validate_cidr
from ..core import colors
from .parser import get

# --- Passwords ---
def validate_passwords(config) -> bool:
    ok = True
    required = ["ADMIN_PASSWORD", "SERVICE_PASSWORD", "RABBITMQ_PASSWORD", "DATABASE_PASSWORD", "DEMO_PASSWORD"]
    for key in required:
        value = get(config, f"passwords.{key}")
        if not value:
            print(f"{colors.RED}Error: passwords.{key} is not set{colors.RESET}")
            ok = False
    return ok

# --- Public network ---
def validate_host_network(config) -> bool:

    ok = True

    host_network_fields = [
        "network.HOST_IP",
        "network.HOST_IP_NETMASK",
    ]

    cidr_fields = ["network.HOST_IP_CIDR"]

    for field in cidr_fields:
        value = get(config, field)
        if not value:
            ok = False
            print(f"{colors.RED}Error: Field '{field}' is missing.{colors.RESET}")
        elif not validate_cidr(value, field):
            ok = False
            print(f"{colors.RED}Error: Field '{field}' has invalid CIDR: {value}{colors.RESET}")

    # Validate IP fields
    for field in host_network_fields:
        value = get(config, field)
        if not value:
            ok = False
            print(f"{colors.RED}Error: Field '{field}' is missing.{colors.RESET}")
        elif not validate_ip(value, field):
            ok = False

    return ok


def validate_public_network(config) -> bool:

    ok = True

    ip_fields = [
        "public_network.PUBLIC_SUBNET_GATEWAY",
        "public_network.PUBLIC_SUBNET_RANGE_START",
        "public_network.PUBLIC_SUBNET_RANGE_END",
    ]
    cidr_fields = ["public_network.PUBLIC_SUBNET_CIDR"]

    # Validate CIDR fields
    for field in cidr_fields:
        value = get(config, field)
        if not value:
            ok = False
            print(f"{colors.RED}Error: Field '{field}' is missing.{colors.RESET}")
        elif not validate_cidr(value, field):
            ok = False
            print(f"{colors.RED}Error: Field '{field}' has invalid CIDR: {value}{colors.RESET}")

    # Validate IP fields
    for field in ip_fields:
        value = get(config, field)
        if not value:
            ok = False
            print(f"{colors.RED}Error: Field '{field}' is missing.{colors.RESET}")
        elif not validate_ip(value, field):
            ok = False
            print(f"{colors.RED}Error: Field '{field}' has invalid IP: {value}{colors.RESET}")

    # Validate DNS servers
    dns_servers = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS", [])
    for i, dns in enumerate(dns_servers):
        if not validate_ip(dns, f"public_network.PUBLIC_SUBNET_DNS_SERVERS[{i}]"):
            ok = False
            print(f"{colors.RED}Error: DNS server at index {i} is invalid: {dns}{colors.RESET}")

    return ok

# --- Neutron ---
def validate_neutron(config) -> bool:
    ok = True
    driver = get(config, "neutron.DRIVER")
    
    ovs_create_bridges = get(config, "neutron.ovs.CREATE_BRIDGES")

    public_bridge_interface_ovs = get(config, "neutron.ovs.PUBLIC_BRIDGE_INTERFACE")

    if driver not in ("ovs", "ovn"):
        print(f"{colors.RED}Error: neutron.DRIVER must be 'ovs' or 'ovn' (got '{driver}'){colors.RESET}")
        ok = False

    if driver == "ovs":
        ovs_fields = [
            "neutron.ovs.PUBLIC_BRIDGE",
            "neutron.ovs.INTERNAL_BRIDGE",
            "neutron.ovs.PUBLIC_BRIDGE_INTERFACE",
        ]
        for field in ovs_fields:
            value = get(config, field)
            if not value:
                print(f"{colors.RED}Error: '{field}' is not set{colors.RESET}")
                ok = False
        
        if ovs_create_bridges not in ("yes", "no"):
            print(f"{colors.RED}Error: '{ovs_create_bridges}' must be 'yes' or 'no' (got '{value}'){colors.RESET}")
            ok = False

        if not interface_exists(public_bridge_interface_ovs):
            print(f"{colors.RED}The interface '{public_bridge_interface_ovs}' specified in neutron.ovs.PUBLIC_BRIDGE_INTERFACE does not exist.{colors.RESET}")
            ok = False


    if driver == "ovn":
        ovn_fields = [
            "neutron.ovn.OVN_PUBLIC_BRIDGE",
            "neutron.ovn.OVN_PUBLIC_BRIDGE_INTERFACE",
            "neutron.ovn.OVN_NB_PORT",
            "neutron.ovn.OVN_SB_PORT",
        ]
        for field in ovn_fields:
            value = get(config, field)
            if not value:
                print(f"{colors.RED}Error: '{field}' is not set{colors.RESET}")
                ok = False

    # Tenant network
    neutron_driver = get(config, "neutron.DRIVER").lower()
    tenant_type = get(config, "neutron.tenant_network.TYPE").lower()
    vni_range = get(config, "neutron.tenant_network.VNI_RANGE").lower()

    networks = get_provider_networks(config)

    for net in networks:
        net_type = net["type"]
        if net_type not in ["geneve", "flat", "vlan"]:
            print(f"{colors.RED}Error: Invalid network type '{net_type}' specified in field {net}{colors.RESET}")
            ok = False

    if tenant_type not in ["geneve", "flat", "vxlan"]:
        print(f"{colors.RED}Error: Invalid network type '{tenant_type}' specified in field neutron.tenant_network.TYPE{colors.RESET}")
        ok = False

    if neutron_driver == "ovn":  
        ovn_encap_type = get(config, "neutron.ovn.OVN_ENCAP_TYPE").lower()

        if not tenant_type and not vni_range:
            print(f"{colors.RED}Error: neutron.tenant_network.TYPE or VNI_RANGE not set{colors.RESET}")
            ok = False

        if ovn_encap_type != tenant_type:
            print(f"{colors.RED}Error: OVN_ENCAP_TYPE ({ovn_encap_type}) "
                f"does not match tenant network type ({tenant_type}).{colors.RESET}")
            ok = False   
    elif neutron_driver == "ovs":
        if not tenant_type:
            print(f"{colors.RED}Error: neutron.tenant_network.TYPE not set{colors.RESET}")
            ok = False

        if tenant_type == "geneve":
            print(f"{colors.RED}Error: neutron.tenant_network type 'geneve' is not supported by OVS{colors.RESET}")
            ok = False
    

    # Provider networks
    provider_networks = get(config, "neutron.provider_networks", [])
    if not provider_networks:
        print(f"{colors.RED}Error: neutron.provider_networks is empty{colors.RESET}")
        ok = False
    else:
        for i, net in enumerate(provider_networks):
            if not net.get("name") or not net.get("bridge") or not net.get("type"):
                print(f"{colors.RED}Error: neutron.provider_networks[{i}] missing required keys{colors.RESET}")
                ok = False

    return ok

# --- Cinder ---
def validate_cinder(config) -> bool:
    ok = True
    cinder_fields = [
        "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_FILE_PATH",
        "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB",
    ]
    for field in cinder_fields:
        value = get(config, field)
        if not value:
            print(f"{colors.RED}Error: '{field}' is not set{colors.RESET}")
            ok = False
    return ok

# --- Compute ---
def validate_compute(config) -> bool:
    ok = True
    warnings = []

    compute_fields = [
        "compute.NOVA_COMPUTE_VIRT_TYPE",
        "compute.CPU_ALLOCATION_RATIO",
        "compute.RAM_ALLOCATION_RATIO",
        "compute.DISK_ALLOCATION_RATIO",
    ]

    ratios = {
        "compute.CPU_ALLOCATION_RATIO": 1.0,
        "compute.RAM_ALLOCATION_RATIO": 1.0,
        "compute.DISK_ALLOCATION_RATIO": 1.0,
    }

    max_warn_ratios = {
        "compute.CPU_ALLOCATION_RATIO": 16.0,
        "compute.RAM_ALLOCATION_RATIO": 8.0,
        "compute.DISK_ALLOCATION_RATIO": 2.0,
    }

    for field in compute_fields:
        value = get(config, field)
        if value is None:
            print(f"{colors.RED}Error: '{field}' is not set{colors.RESET}")
            ok = False

    for key, min_value in ratios.items():
        value = get(config, key)
        try:
            float_val = float(value)
            if float_val < min_value:
                print(f"{colors.RED}Error: {key} must be >= {min_value}, found: {float_val}{colors.RESET}")
                ok = False
            elif float_val > max_warn_ratios[key]:
                warnings.append(f"{key} is unusually high ({float_val})")
        except (TypeError, ValueError):
            print(f"{colors.RED}Error: {key} must be a decimal number, found: {value}{colors.RESET}")
            ok = False

    for w in warnings:
        print(f"{colors.YELLOW}Warning: {w}{colors.RESET}")

    return ok

# --- Optional services ---
def validate_optional_services(config) -> bool:
    ok = True

    services = [
        "optional_services.INSTALL_CINDER",
        "optional_services.INSTALL_HORIZON",
    ]

    for field in services:
        value = get(config, field)
        if value not in ("yes", "no"):
            print(f"{colors.RED}Error: '{field}' must be 'yes' or 'no' (got '{value}'){colors.RESET}")
            ok = False
    return ok

# --- OpenStack ---
def validate_openstack(config) -> bool:
    ok = True
    fields = ["openstack.OPENSTACK_RELEASE", "openstack.REGION_NAME"]
    for field in fields:
        value = get(config, field)
        if not value:
            print(f"{colors.RED}Error: '{field}' is not set{colors.RESET}")
            ok = False
    return ok

def validate_all(config) -> bool:
    ok = True
    ok &= validate_passwords(config)
    ok &= validate_host_network(config)
    ok &= validate_public_network(config)
    ok &= validate_neutron(config)
    ok &= validate_cinder(config)
    ok &= validate_compute(config)
    ok &= validate_optional_services(config)
    ok &= validate_openstack(config)
    return ok