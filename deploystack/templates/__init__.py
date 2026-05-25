import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _t(*parts) -> str:
    return os.path.join(BASE_DIR, *parts)

# Cinder
CINDER_LOOPBACK_SERVICE         = _t("cinder", "cinder-loopback.service")
CINDER_LOOPBACK_START_SCRIPT    = _t("cinder", "cinder-loopback-start.sh.tpl")
CINDER_LOOPBACK_STOP_SCRIPT     = _t("cinder", "cinder-loopback-stop.sh.tpl")
CINDER_LVM_ENV_CONF             = _t("cinder", "cinder-lvm-env-conf.tpl")

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