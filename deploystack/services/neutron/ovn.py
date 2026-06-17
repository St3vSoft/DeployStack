# Configure the Open Virtual Network (OVN) Driver for Neutron

import os
import shutil
import json
import time

from ...utils.core.commands import run_command, run_command_sync, os_run, os_run_output
from ...utils.apt.apt import apt_install
from ...utils.config.parser import get
from ...utils.config.setter import set_conf_option
from ...utils.core.system_utils import nc_wait, iface_exists
from ...utils.core import colors
from ...utils.core.system_utils import service_exists, is_debian

from ...templates import OVN_BRIDGES_INTERFACES, OVN_DUAL_NIC_BRIDGES_INTERFACES, OVS_PERMISSIONS_SERVICE

from ...utils.config.helpers import parse_bool

from .network.provisioner import create_custom_networks, clean_custom_bridges, add_custom_bridges, bring_up_custom_bridges_ifaces, append_custom_bridges_ifaces_config
from .network.routers import create_custom_network_router

neutron_conf = "/etc/neutron/neutron.conf"
conf_ml2 = "/etc/neutron/plugins/ml2/ml2_conf.ini"
conf_nova = "/etc/nova/nova.conf"

def install_pkgs():

    print()

    ovn_packages = [
        "neutron-metadata-agent",   # still needed for VM metadata (Nova)
        "ovn-central",              # ovn-northd + NB/SB ovsdb-server
        "ovn-host",                 # ovn-controller on compute nodes
        "ovn-common",               # ovn-nbctl, ovn-sbctl tools
        "openvswitch-switch",       # OVS dataplane (required by OVN)
    ]

    if not apt_install(ovn_packages, ux_text="Installing Neutron OVN packages..."):
        return False

    return True

def conf_ovn_bridges(config):
    print()

    INTERFACES_FILE = "/etc/network/interfaces.d/openvswitch"

    public_iface = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE_INTERFACE")
    public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")
    internal_bridge = "br-int" 

    ip_address = get(config, "network.HOST_IP")
    ip_address_netmask = get(config, "network.HOST_IP_NETMASK")
    ip_address_gateway = get(config, "network.HOST_IP_GATEWAY")
    subnet_gateway = get(config, "neutron.public_network.PUBLIC_SUBNET_GATEWAY")
    subnet_dns = get(config, "neutron.public_network.PUBLIC_SUBNET_DNS_SERVERS")
    management_iface = get(config, "network.HOST_MGMT_INTERFACE")

    bridges = get(config, "neutron.bridges", [])

    is_dual_nic = (public_iface != management_iface)

    line1 = False
    custom_bridges = bool(bridges)

    for iface in [public_iface, public_bridge]:
        if iface_exists(iface):
            run_command(["ip", "addr", "flush", "dev", iface], f"Flushing IPs on {iface}", ignore_errors=True)
            run_command(["ip", "link", "set", iface, "down"], f"Bringing {iface} down", ignore_errors=True)

    if not clean_custom_bridges(bridges=bridges) : return False

    line2 = False

    for bridge, port in [(public_bridge, public_iface)]:
        if iface_exists(bridge):
            if not line2 : 
                print()
                line2 = True

            if port:
                run_command(["ovs-vsctl", "--if-exists", "del-port", bridge, port], f"Deleting port {port} from {bridge}", ignore_errors=True)
            run_command(["ovs-vsctl", "--if-exists", "del-br", bridge], f"Deleting bridge {bridge}", ignore_errors=True)

    print()

    if isinstance(subnet_dns, list):
        subnet_dns = " ".join(subnet_dns)

    template_file = OVN_DUAL_NIC_BRIDGES_INTERFACES if is_dual_nic else OVN_BRIDGES_INTERFACES

    if not os.path.exists(template_file):
        print(f"{colors.RED}Error: template file '{template_file}' not found{colors.RESET}")
        return False
    
    with open(template_file, "r") as f:
        template = f.read()

    bridges_interfaces_content = template.format(
        management_iface=management_iface if is_dual_nic else "",
        ip_address=ip_address,
        ip_address_netmask=ip_address_netmask,
        subnet_address_gateway=ip_address_gateway if is_dual_nic else subnet_gateway,
        subnet_address_dns_servers=subnet_dns,
        public_iface=public_iface,
        public_bridge=public_bridge,
    )

    if custom_bridges:
        bridges_interfaces_content = append_custom_bridges_ifaces_config(
            bridges,
            bridges_interfaces_content
        )
        
    with open(INTERFACES_FILE, "w") as f:
        f.write(bridges_interfaces_content)

    interfaces_dir = "/etc/network/interfaces.d/"
    backup_dir = "/root/net-backup"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    for filename in os.listdir(interfaces_dir):
        full_path = os.path.join(interfaces_dir, filename)
        if full_path == INTERFACES_FILE or not os.path.isfile(full_path):
            continue
        backup_name = f"{filename}.{timestamp}"
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.move(full_path, backup_path)

    if not run_command(["ovs-vsctl", "--may-exist", "add-br", public_bridge],
                       f"Adding bridge {public_bridge}"):
        return False
    if not run_command(["ovs-vsctl", "--may-exist", "add-port", public_bridge, public_iface],
                       f"Adding port {public_iface} to {public_bridge}"):
        return False
    
    if custom_bridges:
        if not add_custom_bridges(bridges=bridges) : return False

    print()

    if not run_command(["ip", "link", "set", public_iface, "up"], f"Bringing {public_iface} up"):
        return False
    if not run_command(["ip", "link", "set", public_bridge, "up"], f"Bringing {public_bridge} up"):
        return False
    
    if custom_bridges:
        if not bring_up_custom_bridges_ifaces(bridges=bridges) : return False

    print()

    networking_cmds = [
        "systemctl disable systemd-networkd",
        "systemctl stop systemd-networkd",
        "systemctl enable networking",
        "systemctl restart networking",
    ]

    full_cmd = " && ".join(networking_cmds)

    if not run_command(["bash", "-c", full_cmd], "Restarting Networking service..."): return False

    return True

def conf_ovn_controller(config):

    print()

    ip_address = get(config, "network.HOST_IP")

    ovn_sb_port = get(config, "neutron.ovn.OVN_SB_PORT")
    ovn_encap_type = get(config, "neutron.ovn.OVN_ENCAP_TYPE")
    
    provider_networks = get(config, "neutron.provider_networks", [])

    bridge_mappings = ",".join(
        f'{n["name"]}:{n["bridge"]}'
        for n in provider_networks
        if n.get("type") != "local" and n.get("bridge")
    )

    if not run_command(
        ["ovs-vsctl", "set", "open", ".",
         f"external-ids:ovn-remote=tcp:{ip_address}:{ovn_sb_port}"],
        "Setting OVN remote (SB DB)"
    ) : return False

    if not run_command(
        ["ovs-vsctl", "set", "open", ".",
         f"external-ids:ovn-encap-type={ovn_encap_type}",
         f"external-ids:ovn-encap-ip={ip_address}"],
        "Setting OVN encap type and IP"
    ) : return False

    if not run_command(
        ["ovs-vsctl", "set", "open", ".",
         f"external-ids:ovn-bridge-mappings={bridge_mappings}"],
        "Setting OVN bridge mappings"
    ) : return False

    if not run_command(
        ["ovs-vsctl", "set", "open", ".",
         "external-ids:ovn-cms-options=enable-chassis-as-gw"],
        "Enabling chassis as OVN gateway"
    ) : return False

    return True


def conf_ovn_db_connections(config):

    print()

    ip_address = get(config, "network.HOST_IP")

    ovn_sb_port = get(config, "neutron.ovn.OVN_SB_PORT")
    ovn_nb_port = get(config, "neutron.ovn.OVN_NB_PORT")

    run_command_sync(['ovs-vsctl', 'set-manager', 'ptcp:6640:127.0.0.1'])

    run_command(
        ["ovn-nbctl",
         "--db=unix:/var/run/ovn/ovnnb_db.sock",
         "set-connection", f"ptcp:{ovn_nb_port}:{ip_address}", "--",
         "set", "connection", ".", "inactivity_probe=60000"],
        f"Opening NB DB on TCP {ovn_nb_port}"
    )

    run_command(
        ["ovn-sbctl",
         "--db=unix:/var/run/ovn/ovnsb_db.sock",
         "set-connection", f"ptcp:{ovn_sb_port}:{ip_address}", "--",
         "set", "connection", ".", "inactivity_probe=60000"],
        f"Opening SB DB on TCP {ovn_sb_port}"
    )

    return True

def conf_ovn_neutron(config):

    ip_address = get(config, "network.HOST_IP")

    ovn_sb_port = get(config, "neutron.ovn.OVN_SB_PORT")
    ovn_nb_port = get(config, "neutron.ovn.OVN_NB_PORT")

    tenant_network_type = get(config, "neutron.tenant_network.TYPE", "geneve").lower()
    tenant_network_vni_range = get(config, "neutron.tenant_network.VNI_RANGE", "1:1000")

    ovn_l3_scheduler = get(config, "neutron.ovn.OVN_L3_SCHEDULER", "leastloaded").lower()

    service_password = get(config, "passwords.SERVICE_PASSWORD")
    
    provider_networks = get(config, "neutron.provider_networks", [])

    flat_networks = [n["name"] for n in provider_networks if n["type"] == "flat"]
    vlan_networks = [n for n in provider_networks if n["type"] == "vlan"]

    flat_networks_str = ",".join(flat_networks)
    vlan_networks_str = ",".join(f'{n["name"]}:{n["vlan_range"]}' for n in vlan_networks)

    bridge_mappings = ",".join(
        f'{n["name"]}:{n["bridge"]}'
        for n in provider_networks
        if n.get("name") and n.get("bridge")
    )

    enable_distributed_floating_ip = get(config, "neutron.ovn.ENABLE_DISTRIBUTED_FLOATING_IP", "no") == "yes"

    ovn_encap_type = get(config, "neutron.ovn.OVN_ENCAP_TYPE").lower()

    create_ovn_bridges = get(config, "neutron.ovn.CREATE_BRIDGES", "no") == "yes"

    set_conf_option(conf_ml2, "ml2", "mechanism_drivers", "ovn")
    set_conf_option(conf_ml2, "ml2", "type_drivers", f"flat,vlan,local,{tenant_network_type}")
    set_conf_option(conf_ml2, "ml2", "tenant_network_types", tenant_network_type)
    set_conf_option(conf_ml2, "ml2", "extension_drivers", "port_security")
    set_conf_option(conf_ml2, "securitygroup", "enable_ipset", "true")

    if create_ovn_bridges:
        if ovn_encap_type == "geneve":
            set_conf_option(conf_ml2, "ml2_type_geneve", "vni_ranges", tenant_network_vni_range)
            set_conf_option(conf_ml2, "ml2_type_geneve", "max_header_size", "38")
        elif ovn_encap_type == "vxlan":
            set_conf_option(conf_ml2, "ml2_type_vxlan", "vni_ranges", tenant_network_vni_range)

        if flat_networks_str:
            set_conf_option(conf_ml2, "ml2_type_flat", "flat_networks", flat_networks_str)
        if vlan_networks_str:
            set_conf_option(conf_ml2, "ml2_type_vlan", "network_vlan_ranges", vlan_networks_str)
        
        set_conf_option(conf_ml2, "ovn", "ovn_bridge_mappings", bridge_mappings)

    set_conf_option(conf_ml2, "ovn", "ovn_nb_connection", f"tcp:{ip_address}:{ovn_nb_port}")
    set_conf_option(conf_ml2, "ovn", "ovn_sb_connection", f"tcp:{ip_address}:{ovn_sb_port}")
    set_conf_option(conf_ml2, "ovn", "ovn_l3_mode", "true")
    set_conf_option(conf_ml2, "ovn", "ovn_l3_scheduler", ovn_l3_scheduler)
    set_conf_option(conf_ml2, "ovn", "ovn_metadata_enabled", "true")

    set_conf_option(neutron_conf, "ovn", "enable_distributed_floating_ip", "true" if enable_distributed_floating_ip else "false")

    set_conf_option(conf_nova, "os_vif_ovs", "ovsdb_connection", "unix:/var/run/openvswitch/db.sock")
    set_conf_option(conf_nova, "neutron", "ovs_bridge", "br-int")

    return True

def finalize(config):
    print()

    ip_address = get(config, "network.HOST_IP")

    run_command_sync(["ovs-vsctl", "set-manager",
                      f"ptcp:6640:{ip_address}",
                      "punix:/var/run/openvswitch/db.sock"])
    
    udev_rule = 'SUBSYSTEM=="unix", ACTION=="add", DEVPATH=="/var/run/openvswitch/db.sock", MODE="0666"\n'

    with open("/etc/udev/rules.d/99-openvswitch.rules", "w") as f:
        f.write(udev_rule)

    shutil.copy(OVS_PERMISSIONS_SERVICE, "/etc/systemd/system/ovs-nova-perms.service")

    if not run_command(["systemctl", "daemon-reload"], "Reloading system daemon...") : return False
    if not run_command(["systemctl", "enable", "--now", "ovs-nova-perms.service"], "Enabling OVS Nova Permission Service...") : return False

    print()

    if not run_command(["systemctl", "enable", "--now", "ovn-northd"],
                       "Starting ovn-northd...", False, None, 3, 5):
        return False

    if not run_command(["systemctl", "enable", "--now", "ovn-controller"],
                       "Starting ovn-controller...", False, None, 3, 5):
        return False
    
    print()
    
    if service_exists("nova-api.service"):
        if not run_command(["systemctl", "restart", "nova-api"], "Restarting Nova API...", False, None, 3, 5): return False

    if service_exists("neutron-server.service"):
        if not run_command(
            ["systemctl", "restart",
            "neutron-server",
            "neutron-metadata-agent",
            "nova-compute"],
            "Restarting Neutron and Nova services...", False, None, 3, 5
        ):
            return False
    elif service_exists("neutron-api.service") and is_debian():
        if not run_command(["systemctl", "restart", "neutron-api", "neutron-rpc-server", "neutron-metadata-agent", "nova-compute"], "Restarting Neutron services...", False, None, 3, 5): return False
    else:
        if not run_command(
            ["systemctl", "restart",
            "neutron-periodic-workers", "apache2",
            "neutron-metadata-agent",
            "nova-compute"],
            "Restarting Neutron and Nova services...", False, None, 3, 5
        ):
            return False
        
    printed_line = False
    for svc in ["neutron-l3-agent", "neutron-dhcp-agent", "neutron-openvswitch-agent"]:
        if service_exists(svc):
            if not printed_line:
                print()
                printed_line = True

            run_command(["systemctl", "disable", "--now", svc],
            f"Disabling legacy agent {svc}", ignore_errors=True)

    run_command_sync(["udevadm", "control", "--reload-rules"])

    if not nc_wait(ip_address, 9696) : return False

    return True

def create_ovn_networks(config, env):
    print()

    public_subnet_range_start = get(config, "neutron.public_network.PUBLIC_SUBNET_RANGE_START")
    public_subnet_range_end = get(config, "neutron.public_network.PUBLIC_SUBNET_RANGE_END")
    public_subnet_gateway = get(config, "neutron.public_network.PUBLIC_SUBNET_GATEWAY")
    public_subnet_dns_servers = get(config, "neutron.public_network.PUBLIC_SUBNET_DNS_SERVERS")
    public_subnet_cidr = get(config, "neutron.public_network.PUBLIC_SUBNET_CIDR")

    public_bridge = get(config, "neutron.ovn.OVN_PUBLIC_BRIDGE")
    ovn_encap_type = get(config, "neutron.ovn.OVN_ENCAP_TYPE").lower()

    provider_networks = get(config, "neutron.provider_networks", [])
    public_network = next((n for n in provider_networks if n["name"] == "public"), None)

    create_ovn_bridges = get(config, "neutron.ovn.CREATE_BRIDGES", "no") == "yes"

    dns_args = []
    for dns in public_subnet_dns_servers:
        dns_args.extend(["--dns-nameserver", dns])

    networks_list = json.loads(os_run_output(["openstack", "network", "list", "-f", "json"], env=env))
    subnets_list = json.loads(os_run_output(["openstack", "subnet", "list", "-f", "json"], env=env))
    routers_list = json.loads(os_run_output(["openstack", "router", "list", "-f", "json"], env=env))

    public_network_exists = any(net.get("Name") == "public" for net in networks_list)
    if not public_network_exists:
        net_type = public_network.get("type", "flat") if public_network else "flat"

        if create_ovn_bridges:
            if net_type == "flat":
                create_public_network_cmd = [
                    "openstack", "network", "create",
                    "--share", "--external",
                    "--provider-physical-network", public_network["name"],
                    "--provider-network-type", "flat",
                    "public"
                ]
            elif net_type == "vlan" and public_network.get("vlan_range"):
                start, _ = map(int, public_network["vlan_range"].split(":"))
                vlan_id = start
                create_public_network_cmd = [
                    "openstack", "network", "create",
                    "--share", "--external",
                    "--provider-physical-network", public_network["name"],
                    "--provider-network-type", "vlan",
                    "--provider-segment", str(vlan_id),
                    "public"
                ]
            else:
                create_public_network_cmd = ["openstack", "network", "create", "--share", "--external", "public"]
        else:
            create_public_network_cmd = ["openstack", "network", "create", "--share", "public"]

        if not os_run(create_public_network_cmd, "Creating public network...", env=env):
            return False

        public_subnet_exists = any(sub.get("Name") == "public_subnet" for sub in subnets_list)
        if not public_subnet_exists:
            subnet_cmd = [
                "openstack", "subnet", "create",
                "--network", "public",
                "--allocation-pool", f"start={public_subnet_range_start},end={public_subnet_range_end}",
                "--gateway", public_subnet_gateway,
                "--subnet-range", public_subnet_cidr
            ] + dns_args + ["public_subnet"]

            if not os_run(subnet_cmd, "Creating public subnet...", env=env):
                return False
    else:
        print(f"{colors.YELLOW}Public network already exists, skipping creation.{colors.RESET}")

    print()

    internal_network_exists = any(net.get("Name") == "internal" for net in networks_list)
    create_internal_network_cmd = [
        "openstack", "network", "create",
        "--share",
        "--provider-network-type", ovn_encap_type,
        "internal"
    ] if create_ovn_bridges else ["openstack", "network", "create", "internal"]

    if not internal_network_exists:
        if not os_run(create_internal_network_cmd, f"Creating internal ({ovn_encap_type}) network...", env=env):
            return False
    else:
        print(f"{colors.YELLOW}Internal network already exists, skipping creation.{colors.RESET}")

    internal_subnet_exists = any(sub.get("Name") == "internal_subnet" for sub in subnets_list)
    if not internal_subnet_exists:
        internal_subnet_cmd = [
            "openstack", "subnet", "create",
            "--network", "internal",
            "--subnet-range", "10.0.0.0/24",
            "--gateway", "10.0.0.1",
            "--allocation-pool", "start=10.0.0.10,end=10.0.0.200",
            "--dns-nameserver", "8.8.8.8",
            "internal_subnet"
        ]
        if not os_run(internal_subnet_cmd, "Creating internal subnet...", env=env):
            return False
    else:
        print(f"{colors.YELLOW}Internal subnet already exists, skipping creation.{colors.RESET}")

    if provider_networks:
        
        print()

        if not create_custom_networks(networks_list=networks_list, subnets_list=subnets_list, provider_networks=provider_networks, public_bridge=public_bridge, env=env) :
            return False

    print()

    router_exists = any(r.get("Name") == "internal_router" for r in routers_list)
    if not router_exists:
        if not os_run(["openstack", "router", "create", "internal_router"], "Creating internal router...", env=env):
            return False
    else:
        print(f"{colors.YELLOW}Internal Router already exists, skipping creation.{colors.RESET}")

    if create_ovn_bridges:

        external_gateways_list = json.loads(os_run_output(["openstack", "router", "show", "internal_router", "-f", "json", "-c", "external_gateways"], env=env))
        interfaces_info_list = json.loads(os_run_output(["openstack", "router", "show", "internal_router", "-f", "json", "-c", "interfaces_info"], env=env))

        if not external_gateways_list.get("external_gateways"):
            if not os_run(
                ["openstack", "router", "set", "internal_router", "--external-gateway", "public"],
                "Setting external gateway for internal router...", env=env
            ):
                return False

        if not interfaces_info_list.get("interfaces_info"):
            if not os_run(
                ["openstack", "router", "add", "subnet", "internal_router", "internal_subnet"],
                "Adding internal subnet to router...", env=env
            ):
                return False
            
        if provider_networks:

            print()

            if not create_custom_network_router(subnets_list=subnets_list, routers_list=routers_list, provider_networks=provider_networks, provider_networks=provider_networks, public_bridge=public_bridge, env=env) : return False

    sg_list = json.loads(os_run_output(["openstack", "security", "group", "list", "-f", "json"], env=env))
    default_sg = next((sg for sg in sg_list if sg["Name"] == "default"), None)
    if not default_sg:
        raise RuntimeError("No security group named 'default' found")
    sg_id = default_sg["ID"]

    rules = json.loads(os_run_output(["openstack", "security", "group", "rule", "list", sg_id, "-f", "json"], env=env))

    ssh_rule_exists = any(
        rule.get("IP Protocol") == "tcp" and
        rule.get("Port Range") == "22:22" and
        rule.get("Direction") == "ingress"
        for rule in rules
    )

    if create_ovn_bridges and not ssh_rule_exists:

        print()

        if not os_run(
            ["openstack", "security", "group", "rule", "create",
             "--proto", "tcp", "--dst-port", "22", "--remote-ip", public_subnet_cidr, sg_id],
            "Allowing SSH access...", env=env
        ):
            return False
    else:
        print(f"{colors.YELLOW}SSH rule already exists or skipped.{colors.RESET}")

    icmp_rule_exists = any(rule.get("IP Protocol") == "icmp" for rule in rules)
    if create_ovn_bridges and not icmp_rule_exists:
        print()

        if not os_run(
            ["openstack", "security", "group", "rule", "create",
             "--proto", "icmp", sg_id],
            "Allowing ICMP (ping)...", env=env
        ):
            return False
    else:
        print(f"{colors.YELLOW}ICMP rule already exists or skipped.{colors.RESET}")

    print()

    #if create_ovn_bridges:
    
     #   router_gw_ip = json.loads(os_run_output(["openstack", "router", "show", "internal_router", "-f", "json"], env=env))

      #  gw_ip = router_gw_ip["external_gateway_info"]["external_fixed_ips"][0]["ip_address"]
        #run_command_sync(["ip", "route", "replace", "10.0.0.0/24", "via", gw_ip, "dev", ovn_public_bridge])

    if not run_command([
        "neutron-ovn-db-sync-util",
        "--config-file", "/etc/neutron/neutron.conf",
        "--config-file", "/etc/neutron/plugins/ml2/ml2_conf.ini",
        "--ovn-neutron_sync_mode", "repair"
    ], "Resynchronizing the OVN Northd database..."): return False

    ovs_services =  ["systemctl", "restart",
            "ovn-ovsdb-server-nb",
            "ovn-ovsdb-server-sb",
            "ovn-northd",
            "ovn-controller",
            "nova-compute"]

    if service_exists("neutron-api.service") and not service_exists("neutron-server.service"):
        ovs_services.append("neutron-api")
    else:
        ovs_services.append("neutron-server")
        
    if not run_command(
        ovs_services,
        "Restarting OVN services...", False, None, 3, 5
    ):  return False

    return True

def run_setup_ovn_neutron(config, env):

    #tenant_type = get(config, "neutron.tenant_network.TYPE", "geneve")
    #if tenant_type != "geneve":
    #    print(f"\n{colors.YELLOW}Warning: OVN only supports 'geneve' as tenant network type. "
    #          f"Overriding '{tenant_type}' with 'geneve'.{colors.RESET}")
    #    config["neutron"]["tenant_network"]["TYPE"] = "geneve"

    config_ovn_bridges = get(config, "neutron.ovn.CREATE_BRIDGES", "no") == "yes"

    if not install_pkgs(): return False

    if config_ovn_bridges:
        if not conf_ovn_bridges(config): return False

    if not conf_ovn_neutron(config): return False
    if not conf_ovn_db_connections(config): return False
    if not conf_ovn_controller(config): return False
    if not finalize(config): return False
    if not create_ovn_networks(config, env): return False

    return True