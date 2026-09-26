import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _t(*parts) -> str:
    return os.path.join(BASE_DIR, *parts)

# Loopback
LOOPBACK_SERVICE         = _t("loopback", "loopback.service.tpl")

# Neutron OVS
OVS_BRIDGES_INTERFACES          = _t("openvswitch", "ovs_bridges_interfaces.tpl")
OVS_DUAL_NIC_BRIDGES_INTERFACES = _t("openvswitch", "ovs_bridges_interfaces_dual_nic.tpl")

# Neutron OVN
OVN_BRIDGES_INTERFACES          = _t("openvswitch", "ovn_bridges_interfaces.tpl")
OVN_DUAL_NIC_BRIDGES_INTERFACES = _t("openvswitch", "ovn_bridges_interfaces_dual_nic.tpl")

OVS_PERMISSIONS_SERVICE         = _t("openvswitch", "ovs_perms.service")

# Cloud-init
CLOUD_CONFIG_LINUX              = _t("cloud-config", "linux.yaml")
CLOUD_CONFIG_LINUX_NO_ROOT      = _t("cloud-config", "linux_no_root.yaml")
CLOUD_CONFIG_WINDOWS            = _t("cloud-config", "windows.yaml")

# MySQL
MYSQL_CONFIG                    = _t("mysql", "mysqld.tpl")

# Config
OPENSTACK_CONFIG_TEMPLATE       = _t("openstack", "openstack.yaml")