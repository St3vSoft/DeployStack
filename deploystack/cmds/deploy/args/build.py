from argparse import _MutuallyExclusiveGroup

def add_deployment_arguments(deployment_group, deployment_options):

    deployment_group.add_argument(
        "-aio",
        "--allinone",
        action="store_true",
        help="Runs a complete OpenStack deployment using an automatically generated configuration."
    )

    deployment_group.add_argument(
        "-c",
        "--config-file",
        help="Path to the configuration file"
    )

    deployment_options.add_argument(
        "--generate-only",
        action="store_true",
        help="Generates a pre-compiled configuration file for the current system without starting the deployment"
    )

def add_general_arguments(parser, os_release: str, gateway_group: _MutuallyExclusiveGroup):

    parser.add_argument(
        "--install-horizon",
        type=str,
        choices=["yes", "no"],
        default="yes",
        help="Choosing whether to install Horizon (Dashboard) service (yes/no)"
    )

    parser.add_argument(
        "--neutron-driver",
        type=str,
        choices=["ovs", "ovn"],
        default="ovs",
        dest="neutron_driver",
        help="The Neutron Driver that will be used to configure networks in OpenStack"
    )

    parser.add_argument(
        "--os-release",
        type=str,
        dest="os_release",
        default=os_release,
        help=f"The OpenStack release to install for deployment (default: {os_release})"
    )

    parser.add_argument(
        "--os-management-interface",
        type=str,
        help="Override the OpenStack management network interface used by services (example: eth0, ens18)"
    )

    gateway_group.add_argument(
        "--os-management-gateway",
        type=str,
        default=None,
        help="Override the OpenStack management gateway interface used by services"
    )

    gateway_group.add_argument(
        "--default-gateway",
        type=str,
        default=None,
        help="Default network gateway used by the OpenStack host for outbound traffic."
    )

def add_cinder_arguments(parser):

    parser.add_argument(
        "--install-cinder",
        type=str,
        choices=["yes", "no"],
        default="yes",
        help="Choosing whether to install Cinder (Block Storage) service (yes/no)"
    )

    parser.add_argument(
        "--cinder-enabled-backends",
        nargs="+",
        choices=["lvm", "nfs"],
        dest="cinder_enabled_backends",
        help="One or more Cinder volume backends to enable (choices: lvm, nfs)."
    )

    parser.add_argument(
        "--enable-nfs-snapshots",
        choices=["yes", "no"],
        type=str,
        help="Enable or disable snapshot support for the Cinder NFS driver. (yes/no)"
    )

    cinder_lvm_storage = parser.add_mutually_exclusive_group()

    cinder_lvm_storage.add_argument(
        "--cinder-lvm-image-size-in-gb",
        type=int,
        default=None,
        help="Size of the Cinder LVM image in GB (default: 5)"
    )

    cinder_lvm_storage.add_argument(
        "--cinder-physical-volume",
        type=str,
        default=None,
        help="The physical volume to use for Cinder (example: /dev/sdb)"
    )

    parser.add_argument(
        "--cinder-volume-group",
        type=str,
        default="cinder-volumes",
        help="Name of the LVM volume group. (default: cinder-volumes)"
    )

def add_cinder_backup_arguments(parser): 
    
    parser.add_argument(
        "--enable-cinder-backup",
        type=str,
        choices=["yes", "no"],
        default="no",
        help="Choose whether to enable the Cinder Backup service (yes/no)"
    )

    parser.add_argument(
        "--cinder-backup-driver",
        type=str,
        choices=["posix", "nfs"],
        default=None,
        help="Cinder backup driver to use (posix, nfs)"
    )

    parser.add_argument(
        "--compression-algorithm",
        type=str,
        choices=["zlib", "bz2", "zstd", "none"],
        #default="zlib",
        default=None,
        help="Backup compression algorithm"
    )

    parser.add_argument(
        "--backup-file-size-in-bytes",
        type=int,
        #default=1999994880,
        default=None,
        help="Maximum size of each backup file in bytes (Default: 1999994880)"
    )

    parser.add_argument(
        "--backup-sha-block-size-in-bytes",
        type=int,
        #default=32768,
        default=None,
        help="Block size in bytes used for SHA checksum calculation (Default: 32768)"
    )

    parser.add_argument(
        "--backup-workers",
        type=int,
        #default=1,
        default=None,
        help="Number of concurrent backup operations"
    )

def add_manila_arguments(parser):

    parser.add_argument(
        "--install-manila",
        type=str,
        choices=["yes", "no"],
        default="no",
        help="Choosing whether to install Manila (Shared Filesystems) service (yes/no)"
    )

    manila_lvm_storage = parser.add_mutually_exclusive_group()

    manila_lvm_storage.add_argument(
        "--manila-lvm-physical-volume",
        type=str,
        help="The physical volume to use for Manila LVM (example: /dev/sdc)"
    )
    
    manila_lvm_storage.add_argument(
        "--manila-lvm-image-size-in-gb",
        type=int,
        help="Size of the Manila LVM image in GB (default: 5)"
    )

    manila_lvm_storage.add_argument(
        "--manila-volume-group",
        type=str,
        help="Name of the LVM volume group used for Manila shares"
    )

    parser.add_argument(
        "--manila-backend",
        type=str,
        choices=["generic", "lvm"],
        dest="manila_backend",
        help="The Manila Backend that will be used to configure shares in OpenStack"
    )

    parser.add_argument(
        "--manila-share-protocols",
        nargs="+",
        choices=["nfs", "cifs"],
        dest="manila_share_protocols",
        help="One or more Manila share protocols (choices: nfs, cifs)."
    )

    parser.add_argument(
        "--manila-service-instance-auth-method",
        type=str,
        choices=["password", "ssh_key"],
        dest="manila_service_instance_auth_method",
        help=("Authentication method for Manila service instances "
            "(choices: password, ssh_key; default: ssh_key; Generic backend only)"
        )
    )

def add_nova_compute_arguments(parser):

    parser.add_argument(
        "--virt-type",
        type=str,
        choices=["qemu", "kvm"],
        default="kvm",
        help="Virtualization type. Use kvm on bare metal, qemu inside a virtual machine (nested virtualization). (default: kvm)"
    )

    parser.add_argument(
        "--cpu-allocation-ratio",
        type=float,
        default=2.0,
        help="Overcommit ratio for vCPUs (default: 2.0)"
    )

    parser.add_argument(
        "--ram-allocation-ratio",
        type=float,
        default=1.5,
        help="Overcommit ratio for RAM. (default: 1.5)"
    )

    parser.add_argument(
        "--disk-allocation-ratio",
        type=float,
        default=1.5,
        help="Overcommit ratio for disk. (default: 1.5)"
    )

    parser.add_argument(
        "--allow-resize-to-same-host",
        type=str,
        choices=["yes", "no"],
        default="no",
        help="Allow resize operations to be performed on the same compute host. (default: no)"
    )