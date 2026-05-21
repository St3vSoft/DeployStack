# Configure the OpenvSwitch (OVS) Driver for Neutron

import os
import shutil
import json

from ...utils.core.commands import run_command, run_command_sync, run_command_output
from ...utils.apt.apt import apt_install
from ...utils.config.parser import get
from ...utils.config.setter import set_conf_option
from ...utils.core.system_utils import nc_wait, iface_exists
from ...utils.core import colors
from ...utils.core.system_utils import service_exists
from ...templates import OVS_BRIDGES_INTERFACES

neutron_conf="/etc/neutron/neutron.conf"
conf_ml2="/etc/neutron/plugins/ml2/ml2_conf.ini"
conf_openvswitch="/etc/neutron/plugins/ml2/openvswitch_agent.ini"
conf_dhcp_agent="/etc/neutron/dhcp_agent.ini"
conf_metadata_agent="/etc/neutron/metadata_agent.ini"
conf_l3_agent="/etc/neutron/l3_agent.ini"
conf_nova="/etc/nova/nova.conf"

def install_pkgs():

    print()

    ovs_packages = [
        "neutron-openvswitch-agent", 
        "neutron-dhcp-agent", 
        "neutron-metadata-agent", 
        "neutron-l3-agent", 
        "openvswitch-switch"]

    if not apt_install(ovs_packages, ux_text=f"Installing OVS packages...") : return False

    return True

def conf_openvswitch_bridges(config):

    print()
      
    INTERFACES_FILE = "/etc/network/interfaces.d/openvswitch"

    public_iface = get(config, "neutron.ovs.PUBLIC_BRIDGE_INTERFACE")
    public_bridge = get(config, "neutron.ovs.PUBLIC_BRIDGE")
    internal_bridge = get(config, "neutron.ovs.INTERNAL_BRIDGE")

    ip_address = get(config, "network.HOST_IP")
    ip_address_netmask = get(config, "network.HOST_IP_NETMASK")

    subnet_gateway = get(config, "public_network.PUBLIC_SUBNET_GATEWAY")
    subnet_dns = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS")

    for iface in [public_iface, public_bridge, internal_bridge]:
        if iface_exists(iface):
            if iface != internal_bridge:
                run_command(["ip", "addr", "flush", "dev", iface], f"Flushing IPs on {iface}", ignore_errors=True)
            run_command(["ip", "link", "set", iface, "down"], f"Bringing {iface} down", ignore_errors=True)

    for bridge, port in [(public_bridge, public_iface), (internal_bridge, None)]:
        if iface_exists(bridge):
            if port:
                run_command(["ovs-vsctl", "--if-exists", "del-port", bridge, port], f"Deleting port {port} from {bridge}", ignore_errors=True)
            run_command(["ovs-vsctl", "--if-exists", "del-br", bridge], f"Deleting bridge {bridge}", ignore_errors=True)

    print()

    with open(OVS_BRIDGES_INTERFACES, "r") as f:
        template = f.read()

    if isinstance(subnet_dns, list):
        subnet_dns = " ".join(subnet_dns)

    bridges_interfaces_content = template.format(
        public_iface=public_iface,
        public_bridge=public_bridge,
        ip_address=ip_address,
        ip_address_netmask=ip_address_netmask,
        subnet_address_gateway=subnet_gateway,
        subnet_address_dns_servers=subnet_dns,
        internal_bridge=internal_bridge
    )

    with open(INTERFACES_FILE, "w") as f:
        f.write(bridges_interfaces_content)

    interfaces_dir = "/etc/network/interfaces.d/"
    backup_dir = "/root/net-backup"
    os.makedirs(backup_dir, exist_ok=True)

    for f in os.listdir(interfaces_dir):
        full_path = os.path.join(interfaces_dir, f)
        backup_path = os.path.join(backup_dir, f)

        if full_path != INTERFACES_FILE and os.path.isfile(full_path):
            if os.path.exists(backup_path):
                os.remove(backup_path)
            shutil.move(full_path, backup_path)

    for bridge, port in [(public_bridge, public_iface), (internal_bridge, None)]:
        if not run_command(["ovs-vsctl", "--may-exist", "add-br", bridge], f"Adding bridge {bridge}"):
            return False
        if port:
            if not run_command(["ovs-vsctl", "--may-exist", "add-port", bridge, port], f"Adding port {port} to {bridge}"):
                return False
            
            print()

            if not run_command(["ip", "link", "set", port, "up"], f"Bringing interface {port} up"):
                return False

        if not run_command(["ip", "link", "set", bridge, "up"], f"Bringing bridge {bridge} up"):
            return False

    print()

    networking_cmds = [
        "systemctl disable systemd-networkd",
        "systemctl stop systemd-networkd",
        "systemctl enable networking",
        "systemctl restart networking",
    ]
    full_cmd = " ; ".join(networking_cmds)
    if not run_command(["bash", "-c", full_cmd], "Restarting Networking service..."):
        return False

    return True

def conf_neutron_ovs(config):

    service_password = get(config, "passwords.SERVICE_PASSWORD")

    ip_address = get(config, "network.HOST_IP")

    public_bridge = get(config, "neutron.ovs.PUBLIC_BRIDGE")
    internal_bridge = get(config, "neutron.ovs.INTERNAL_BRIDGE")

    tenant_network_type = get(config, "neutron.tenant_network.TYPE")

    provider_networks = get(config, "neutron.provider_networks", [])

    flat_networks  = [n["name"] for n in provider_networks if n["type"] == "flat"]
    vlan_networks  = [n["name"] for n in provider_networks if n["type"] == "vlan"]

    bridge_mappings = ",".join(f'{n["name"]}:{n["bridge"]}' for n in provider_networks)

    flat_networks_str = ",".join(flat_networks)

    vlan_networks_str = ",".join(vlan_networks)

    create_ovs_bridges = get(config, "neutron.ovs.CREATE_BRIDGES", "no") == "yes" 

    set_conf_option(conf_ml2, "ml2", "type_drivers", "flat,vlan,local")
    set_conf_option(conf_ml2, "ml2", "tenant_network_types", tenant_network_type)
    set_conf_option(conf_ml2, "ml2", "extension_drivers", "port_security")

    if create_ovs_bridges:
        if flat_networks_str:
            set_conf_option(conf_ml2, "ml2_type_flat", "flat_networks", flat_networks_str)

        if vlan_networks_str:
            set_conf_option(conf_ml2, "ml2_type_vlan", "network_vlan_ranges", vlan_networks_str)

    set_conf_option(conf_ml2, "securitygroup", "enable_ipset", "true")
    set_conf_option(conf_ml2, "ml2", "mechanism_drivers", "openvswitch")

    set_conf_option(conf_openvswitch, "ovs", "integration_bridge", "br-int")
    set_conf_option(conf_openvswitch, "ovs", "bridge_mappings", bridge_mappings)
    set_conf_option(conf_openvswitch, "securitygroup", "enable_security_group", "true")
    set_conf_option(conf_openvswitch, "securitygroup", "firewall_driver", "openvswitch")

    set_conf_option(conf_dhcp_agent, "DEFAULT", "interface_driver", "neutron.agent.linux.interface.OVSInterfaceDriver")
    set_conf_option(conf_dhcp_agent, "DEFAULT", "dhcp_driver", "neutron.agent.linux.dhcp.Dnsmasq")
    set_conf_option(conf_dhcp_agent, "DEFAULT", "enable_isolated_metadata", "true")

    set_conf_option(conf_metadata_agent, "DEFAULT", "nova_metadata_host", ip_address)
    set_conf_option(conf_metadata_agent, "DEFAULT", "metadata_proxy_shared_secret", service_password)

    set_conf_option(conf_l3_agent, "DEFAULT", "interface_driver", "neutron.agent.linux.interface.OVSInterfaceDriver")
    set_conf_option(conf_l3_agent, "DEFAULT", "external_network_bridge", "")
    set_conf_option(conf_l3_agent, "DEFAULT", "use_namespaces", "true")
    set_conf_option(conf_l3_agent, "DEFAULT", "debug", "true")

    return True

def finalize(config):
           
    print()

    ip_address = get(config, "network.HOST_IP")

    if service_exists("nova-api.service"):
        if not run_command(["systemctl", "restart", "nova-api"], "Restarting Nova API...", False, None, 3, 5): return False
  
    if service_exists("neutron-server.service"):
        if not run_command(["systemctl", "restart", "neutron-server", "neutron-openvswitch-agent", "neutron-dhcp-agent", "neutron-metadata-agent", "neutron-l3-agent", "nova-compute"], "Restarting Neutron OVS services...", False, None, 3, 5): return False
    elif service_exists("neutron-api.service"):
        if not run_command(["systemctl", "restart", "neutron-api", "neutron-rpc-server", "neutron-l3-agent", "neutron-openvswitch-agent", "neutron-metadata-agent", "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False  
    else:
        if not run_command(["systemctl", "restart", "neutron-periodic-workers", "apache2", "neutron-openvswitch-agent", "neutron-dhcp-agent", "neutron-metadata-agent", "neutron-l3-agent", "nova-compute"], "Restarting Neutron OVS services...", False, None, 3, 5): return False

    if not nc_wait(ip_address, 9696) : return False

    return True

def create_ovs_networks(config):
     
    print()
    
    ip_address = get(config, "network.HOST_IP")

    admin_password = get(config, "passwords.ADMIN_PASSWORD")

    public_subnet_range_start = get(config, "public_network.PUBLIC_SUBNET_RANGE_START")
    public_subnet_range_end = get(config, "public_network.PUBLIC_SUBNET_RANGE_END")

    public_subnet_gateway = get(config, "public_network.PUBLIC_SUBNET_GATEWAY")
     
    public_subnet_dns_servers = get(config, "public_network.PUBLIC_SUBNET_DNS_SERVERS")

    public_subnet_cidr = get(config, "public_network.PUBLIC_SUBNET_CIDR")   

    provider_networks = get(config, "neutron.provider_networks", [])
    public_network = next((n for n in provider_networks if n["name"] == "public"), None)

    create_ovs_bridges = get(config, "neutron.ovs.CREATE_BRIDGES", "no") == "yes" 

    dns_args = []
    for dns in public_subnet_dns_servers:
        dns_args.extend(["--dns-nameserver", dns])

    os.environ["OS_USERNAME"] = "admin"
    os.environ["OS_PASSWORD"] = admin_password
    os.environ["OS_PROJECT_NAME"] = "admin"
    os.environ["OS_USER_DOMAIN_NAME"] = "Default"
    os.environ["OS_PROJECT_DOMAIN_NAME"] = "Default"
    os.environ["OS_AUTH_URL"] = f"http://{ip_address}:5000/v3"
    os.environ["OS_IDENTITY_API_VERSION"] = "3"

    networks_list_json = run_command_output(["openstack", "network", "list", "-f", "json"])
    subnets_list_json = run_command_output(["openstack", "subnet", "list", "-f", "json"])
    routers_list_json = run_command_output(["openstack", "router", "list", "-f", "json"])

    networks_list = json.loads(networks_list_json)
    subnets_list = json.loads(subnets_list_json)
    routers_list = json.loads(routers_list_json)

    create_flat_public_network_cmd = [
        "openstack", "network", "create",
                "--share", "--external",
                "--provider-physical-network", public_network["name"],
                "--provider-network-type", "flat",
                "public"
    ]

    create_flat_internal_network_cmd = ["openstack", "network", "create", "--share",
                "--provider-physical-network", "internal",
                "--provider-network-type", "flat", "internal"]

    create_public_network_cmd = []
    create_internal_network_cmd = []

    if create_ovs_bridges:
        create_public_network_cmd = create_flat_public_network_cmd
        create_internal_network_cmd = create_flat_internal_network_cmd
    else:
        create_public_network_cmd = ["openstack", "network", "create", "--share", "public"]
        create_internal_network_cmd = ["openstack", "network", "create", "internal"]

    public_network_exists = any(net.get("Name") == "public" for net in networks_list)
    if not public_network_exists:
            if not run_command(
                create_public_network_cmd,
                "Creating public network..."
            ) : return False
    else:
            print(f"{colors.YELLOW}Public network already exists, skipping creation.{colors.RESET}")

    public_subnet_exists = any(sub.get("Name") == "public_subnet" for sub in subnets_list)
    if not public_subnet_exists:
        if not run_command(
            ["openstack", "subnet", "create",
            "--network", "public",
            "--allocation-pool", f"start={public_subnet_range_start},end={public_subnet_range_end}",
            "--gateway", public_subnet_gateway,
            "--subnet-range", public_subnet_cidr,
            "public_subnet"] + dns_args,
            "Creating public subnet..."
        ) : return False
    else:
        print(f"{colors.YELLOW}Public subnet already exists, skipping creation.{colors.RESET}")
    
    print()

    internal_network_exists = any(net.get("Name") == "internal" for net in networks_list)

    if not internal_network_exists:
        if not run_command(
            create_internal_network_cmd,
            "Creating internal network...",
            ) : return False
    else:
        print(f"{colors.YELLOW}Internal network already exists, skipping creation.{colors.RESET}")

    internal_subnet_exists = any(sub.get("Name") == "internal_subnet" for sub in subnets_list)
    if not internal_subnet_exists:
        if not run_command(
            ["openstack", "subnet", "create", "--network", "internal",
            "--subnet-range", "10.0.0.0/24",
            "--gateway", "10.0.0.1",
            "--allocation-pool", "start=10.0.0.10,end=10.0.0.200",
            "--dns-nameserver", "8.8.8.8",
            "internal_subnet"],
            "Creating internal subnet...",
            ) : return False
    else:
        print(f"{colors.YELLOW}Internal subnet already exists, skipping creation.{colors.RESET}")
        
    print()

    router_exists = any(r.get("Name") == "internal_router" for r in routers_list)
    if not router_exists:
        if not run_command(
            ["openstack", "router", "create", "internal_router"],
            "Creating internal router...",
        ): return False

        if create_ovs_bridges:
            if not run_command(
                ["openstack", "router", "set", "internal_router", "--external-gateway", "public"],
                "Setting external gateway for internal router...",
            ): return False

        print()

        if not run_command(
            ["openstack", "router", "add", "subnet", "internal_router", "internal_subnet"],
            "Adding internal subnet to router...",
        ): return False
    else:
        print(f"{colors.YELLOW}Internal Router already exists, skipping creation.{colors.RESET}")
    
    print()

    sg_list_json = run_command_output(["openstack", "security", "group", "list", "-f", "json"])
    sg_list = json.loads(sg_list_json)

    matching_sgs = [sg for sg in sg_list if sg["Name"] == "default"]
    if not matching_sgs:
        raise RuntimeError("No security group named 'default' found")
    sg_id = matching_sgs[0]["ID"]

    rules_json = run_command_output(["openstack", "security", "group", "rule", "list", sg_id, "-f", "json"])
    rules = json.loads(rules_json)

    ssh_rule_exists = any(
        rule.get("IP Protocol") == "tcp" and
        rule.get("Port Range") == "22:22" and
        rule.get("IP Range") == public_subnet_cidr and
        rule.get("Direction") == "ingress"
        for rule in rules
    )

    if create_ovs_bridges and not ssh_rule_exists:
        if not run_command(
            ["openstack", "security", "group", "rule", "create",
            "--proto", "tcp",
            "--dst-port", "22",
            "--remote-ip", public_subnet_cidr,
            sg_id],
            "Allowing SSH access..."): 
            return False
    else:
        print(f"{colors.YELLOW}SSH rule skipped (no OVS bridge or already exists).{colors.RESET}")

    return True

def run_setup_ovs_neutron(config):

    tenant_type = get(config, "neutron.tenant_network.TYPE", "geneve")
    if tenant_type == "geneve":
        print(f"\n{colors.YELLOW}Warning: OVS does not support 'geneve' as tenant network type. "
              f"Overriding with 'flat'.{colors.RESET}")
        config["neutron"]["tenant_network"]["TYPE"] = "flat"
     
    create_ovs_bridges = get(config, "neutron.ovs.CREATE_BRIDGES", "no") == "yes"

    if not install_pkgs(): return False
    
    if create_ovs_bridges:
        if not conf_openvswitch_bridges(config) : return False
    
    if not conf_neutron_ovs(config) : return False
    if not finalize(config) : return False   
    if not create_ovs_networks(config): return False

    return True
