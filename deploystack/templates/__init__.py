import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _t(*parts) -> str:
    return os.path.join(BASE_DIR, *parts)

# Loopback
LOOPBACK_SERVICE         = _t("loopback", "loopback.service.tpl")
LOOPBACK_START_SCRIPT    = _t("loopback", "loopback-start.sh.tpl")
LOOPBACK_STOP_SCRIPT     = _t("loopback", "loopback-stop.sh.tpl")
LVM_ENV_CONF             = _t("loopback", "lvm-env-conf.tpl")

# Manila
MANILA_LVM_NETWORK_SERVICE  = _t("manila", "manila_lvm_network.service")
MANILA_BRIDGE_IP_SCRIPT     = _t("manila", "manila-lvm-br-ip.sh.tpl")

# Neutron OVS
OVS_BRIDGES_INTERFACES          = _t("openvswitch", "ovs_bridges_interfaces.tpl")
OVS_DUAL_NIC_BRIDGES_INTERFACES = _t("openvswitch", "ovs_bridges_interfaces_dual_nic.tpl")

# Neutron OVN
OVN_BRIDGES_INTERFACES          = _t("openvswitch", "ovn_bridges_interfaces.tpl")
OVN_DUAL_NIC_BRIDGES_INTERFACES          = _t("openvswitch", "ovn_bridges_interfaces_dual_nic.tpl")

OVS_PERMISSIONS_SERVICE         = _t("openvswitch", "ovs_perms.service")

# Cloud-init
CLOUD_CONFIG_LINUX              = _t("cloud-config", "linux.yaml")
CLOUD_CONFIG_LINUX_NO_ROOT      = _t("cloud-config", "linux_no_root.yaml")

# MySQL
MYSQL_CONFIG                    = _t("mysql", "mysqld.tpl")

# Config
OPENSTACK_CONFIG_TEMPLATE       = _t("openstack", "openstack.yaml")