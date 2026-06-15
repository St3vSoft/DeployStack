import shutil
import subprocess
import os
import ipaddress

from .helpers import get_provider_networks, interface_exists, validate_ip, validate_cidr, is_loop_device, validate_ip_in_network
from ..core import colors
from .parser import get

from ...utils.config.helpers import parse_bool

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

    # Validazione IP singoli
    for field in host_network_fields:
        value = get(config, field)
        if not value:
            ok = False
            print(f"{colors.RED}Error: Field '{field}' is missing.{colors.RESET}")
        elif not validate_ip(value, field):
            ok = False

    dns_list = get(config, "network.HOST_DNS_SERVERS")
    if not dns_list:
        ok = False
        print(f"{colors.RED}Error: Field 'network.HOST_DNS_SERVERS' is missing.{colors.RESET}")
    else:
        for dns in dns_list:
            if not validate_ip(dns, "network.HOST_DNS_SERVERS"):
                ok = False

    return ok


def validate_public_network(config) -> bool:

    ok = True

    ip_fields = [
        "neutron.public_network.PUBLIC_SUBNET_GATEWAY",
        "neutron.public_network.PUBLIC_SUBNET_RANGE_START",
        "neutron.public_network.PUBLIC_SUBNET_RANGE_END",
    ]
    cidr_fields = ["neutron.public_network.PUBLIC_SUBNET_CIDR"]

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
    dns_servers = get(config, "neutron.public_network.PUBLIC_SUBNET_DNS_SERVERS", [])
    for i, dns in enumerate(dns_servers):
        if not validate_ip(dns, f"neutron.public_network.PUBLIC_SUBNET_DNS_SERVERS[{i}]"):
            ok = False
            print(f"{colors.RED}Error: DNS server at index {i} is invalid: {dns}{colors.RESET}")

    return ok

# --- Neutron ---
def validate_neutron(config) -> bool:
    ok = True

    neutron_driver = (get(config, "neutron.DRIVER") or "").lower()
    tenant_type = (get(config, "neutron.tenant_network.TYPE") or "").lower()
    ovs_create_bridges = get(config, "neutron.ovs.CREATE_BRIDGES")
    public_bridge_interface_ovs = get(config, "neutron.ovs.PUBLIC_BRIDGE_INTERFACE")
    ovn_encap_type = (get(config, "neutron.ovn.OVN_ENCAP_TYPE") or "").lower()

    # Validazione driver
    if neutron_driver not in ("ovs", "ovn"):
        print(f"{colors.RED}Error: neutron.DRIVER must be 'ovs' or 'ovn' (got '{neutron_driver}'){colors.RESET}")
        ok = False

    # ==========================
    # OVS
    # ==========================
    if neutron_driver == "ovs":
        ovs_fields = [
            "neutron.ovs.PUBLIC_BRIDGE",
            "neutron.ovs.INTERNAL_BRIDGE",
            "neutron.ovs.PUBLIC_BRIDGE_INTERFACE"
        ]
        if tenant_type == "vxlan":
            ovs_fields.append("neutron.ovs.TUNNEL_BRIDGE")

        for field in ovs_fields:
            value = get(config, field)
            if not value:
                print(f"{colors.RED}Error: '{field}' is not set{colors.RESET}")
                ok = False

        if ovs_create_bridges not in ("yes", "no"):
            print(f"{colors.RED}Error: 'neutron.ovs.CREATE_BRIDGES' must be 'yes' or 'no' (got '{ovs_create_bridges}'){colors.RESET}")
            ok = False

        if public_bridge_interface_ovs and not interface_exists(public_bridge_interface_ovs):
            print(f"{colors.RED}The interface '{public_bridge_interface_ovs}' specified in neutron.ovs.PUBLIC_BRIDGE_INTERFACE does not exist.{colors.RESET}")
            ok = False

        if tenant_type == "geneve":
            print(f"{colors.RED}Error: neutron.tenant_network.TYPE 'geneve' is not supported by OVS{colors.RESET}")
            ok = False

        if tenant_type == "vxlan":
            vni_range = (get(config, "neutron.tenant_network.VNI_RANGE") or "").lower()
            if not vni_range:
                print(f"{colors.RED}Error: VNI_RANGE must be set for VXLAN tenant networks{colors.RESET}")
                ok = False

    # ==========================
    # OVN
    # ==========================
    if neutron_driver == "ovn":
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

        if ovn_encap_type and tenant_type and ovn_encap_type != tenant_type:
            print(f"{colors.RED}Error: OVN_ENCAP_TYPE ({ovn_encap_type}) does not match tenant network type ({tenant_type}).{colors.RESET}")
            ok = False

    # ==========================
    # Provider networks
    # ==========================
    provider_networks = get(config, "neutron.provider_networks", [])
    if not provider_networks:
        print(f"{colors.RED}Error: neutron.provider_networks is empty{colors.RESET}")
        ok = False
    else:
        for i, net in enumerate(provider_networks):
            net_type = net.get("type")
            net_name = net.get("name")
            prefix = f"provider_networks[{i}] ('{net_name}')"

            if not net_name:
                print(f"{colors.RED}Error: neutron.provider_networks[{i}] missing required key 'name'{colors.RESET}")
                ok = False
                continue

            if net_type not in ["flat", "vlan", "local"]:
                print(f"{colors.RED}Error: Invalid network type '{net_type}' in {prefix}{colors.RESET}")
                ok = False
                continue

            if net_type != "local" and not net.get("bridge"):
                print(f"{colors.RED}Error: {prefix} requires 'bridge' for type '{net_type}'{colors.RESET}")
                ok = False

            subnet = net.get("subnet")
            if subnet:
                cidr = subnet.get("cidr")

                # cidr
                if not cidr:
                    print(f"{colors.RED}Error: {prefix} subnet missing 'cidr'{colors.RESET}")
                    ok = False
                else:
                    if not validate_cidr(cidr, f"{prefix} subnet.cidr", colors):
                        ok = False

                    # gateway
                    gateway = subnet.get("gateway")
                    if gateway:
                        if not validate_ip(gateway, f"{prefix} subnet.gateway", colors):
                            ok = False
                        elif not validate_ip_in_network(gateway, cidr, f"{prefix} subnet.gateway", colors):
                            ok = False

                    # range start/end
                    net_range = subnet.get("range", {})
                    start = net_range.get("start")
                    end = net_range.get("end")

                    if start:
                        if not validate_ip(start, f"{prefix} subnet.range.start", colors):
                            ok = False
                        elif not validate_ip_in_network(start, cidr, f"{prefix} subnet.range.start", colors):
                            ok = False

                    if end:
                        if not validate_ip(end, f"{prefix} subnet.range.end", colors):
                            ok = False
                        elif not validate_ip_in_network(end, cidr, f"{prefix} subnet.range.end", colors):
                            ok = False

                    # coerenza start < end
                    if start and end:
                        try:
                            if ipaddress.ip_address(start) >= ipaddress.ip_address(end):
                                print(f"{colors.RED}Error: {prefix} subnet.range.start must be less than range.end{colors.RESET}")
                                ok = False
                        except ValueError:
                            pass  # già catturato sopra

                    # dns
                    dns_list = subnet.get("dns", [])
                    for j, dns in enumerate(dns_list):
                        if not validate_ip(dns, f"{prefix} subnet.dns[{j}]", colors):
                            ok = False

        if tenant_type not in ["geneve", "vxlan"]:
            print(f"{colors.RED}Error: Invalid tenant network type '{tenant_type}'{colors.RESET}")
            ok = False

        return ok

# --- Cinder ---
def validate_cinder(config) -> bool:
    ok = True

    size_raw = (get(config, "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB") or "")
    path = (get(config, "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_FILE_PATH") or "").lower()
    pv = (get(config, "cinder.lvm.PHYSICAL_VOLUME") or "").lower()

    if pv:
        if not os.path.exists(pv):
            print(f"{colors.RED}Error: PHYSICAL_VOLUME '{pv}' does not exist{colors.RESET}")
            ok = False
            return False

        if not pv.startswith("/dev/") or pv.startswith("/dev/loop") or is_loop_device(pv):
            print(f"{colors.RED}Error: loop devices are not allowed as Physical Volume ({pv}){colors.RESET}")
            ok = False
            return False
    else:
        size = None
        if size_raw:
            try:
                size = int(size_raw)
            except ValueError:
                print(f"{colors.RED}Error: invalid integer for CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB{colors.RESET}")
                ok = False

        required_fields = [
            "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_FILE_PATH",
            "cinder.lvm.CINDER_VOLUME_LVM_IMAGE_SIZE_IN_GB",
            "cinder.lvm.CINDER_VOLUME_LVM_PHYSICAL_PV_LOOP_PATH",
        ]

        for field in required_fields:
            if not get(config, field) :
                print(f"{colors.RED}Error: '{field}' is not set{colors.RESET}")
                ok = False

        if path:
            directory = os.path.dirname(path) or "/"

            while not os.path.exists(directory):
                parent = os.path.dirname(directory)
                if parent == directory:
                    directory = "/"
                    break
                directory = parent

            try:
                _, _, free = shutil.disk_usage(directory)
                free_gb = free / (1024**3)

                if size is not None and size > free_gb:
                    print(
                        f"{colors.RED}Error: insufficient disk space. "
                        f"Required: {size} GB, available: {free_gb:.2f} GB{colors.RESET}"
                    )
                    ok = False

            except FileNotFoundError:
                print(f"{colors.RED}Error: cannot determine disk usage for {directory}{colors.RESET}")
                ok = False

    return ok

# --- Compute ---
def validate_compute(config) -> bool:
    ok = True
    warnings = []

    nova_compute_virt_type = get(config, "compute.NOVA_COMPUTE_VIRT_TYPE" or "").lower()

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

    if nova_compute_virt_type not in ("kvm", "qemu"):
        print(
            f"{colors.RED}Error: unsupported virt_type '{nova_compute_virt_type}'. "
            f"Allowed values are 'kvm' and 'qemu'.{colors.RESET}"
        )
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
    install_cinder = parse_bool(get(config, "optional_services.INSTALL_CINDER", False))

    ok = True
    ok &= validate_passwords(config)
    ok &= validate_host_network(config)
    ok &= validate_public_network(config)
    ok &= validate_neutron(config)

    if install_cinder:
        ok &= validate_cinder(config)

    ok &= validate_compute(config)
    ok &= validate_optional_services(config)
    ok &= validate_openstack(config)
    return ok