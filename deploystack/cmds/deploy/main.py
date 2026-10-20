import ipaddress
import sys
import os

from ...utils.core import colors

from ...utils.core.system_utils import is_ubuntu_release, is_debian
from ...utils.config.helpers import parse_bool

from .generator import generate_config_file, generate_openstack_config

from .runner import deploy as start_deployment

from .args.build import (add_general_arguments, add_deployment_arguments, add_cinder_arguments, add_cinder_backup_arguments, add_nova_compute_arguments, add_manila_arguments)
from .args.validator import validate_deploy_args

from .config import OpenStackConfig, CinderConfig, ManilaConfig, NovaComputeConfig, CinderBackupConfig

def get_default_openstack_release():

    if is_debian():
        return "epoxy"

    ubuntu_releases = {
        "20.04": "ussuri",
        "22.04": "yoga",
        "23.04": "antelope",
        "23.10": "bobcat",
        "24.04": "caracal",
        "24.10": "dalmatian",
        "25.04": "epoxy",
        "25.10": "epoxy",
        "26.04": "gazpacho",
        "26.10": "hibiscus"
    }

    for ubuntu_version, openstack_release in ubuntu_releases.items():
        if is_ubuntu_release(ubuntu_version, exact=True):
            return openstack_release

    return "caracal"

def init_parser(subparsers):
     
    parser = subparsers.add_parser(
        "deploy",
        help="Start the OpenStack Deployment on the current node"
    )

    deployment_options = parser.add_argument_group("Deployment Options")
    general_options = parser.add_argument_group("General Options")

    deployment_group = deployment_options.add_mutually_exclusive_group(required=True)
    gateway_group = general_options.add_mutually_exclusive_group(required=False)

    cinder = parser.add_argument_group("Cinder Options")
    cinder_backup = parser.add_argument_group("Cinder Backup Options")
    nova_compute = parser.add_argument_group("Nova Compute Options")
    manila = parser.add_argument_group("Manila Options")

    default_os_release = get_default_openstack_release()

    add_deployment_arguments(deployment_group, deployment_options)
    add_general_arguments(general_options, default_os_release, gateway_group)

    add_cinder_arguments(cinder)
    add_cinder_backup_arguments(cinder_backup)

    add_nova_compute_arguments(nova_compute)

    add_manila_arguments(manila)

    parser.set_defaults(cmd_parser=parser)

    return parser

def deploy(parser, args) -> None:

    parser = args.cmd_parser

    if args.allinone:

        validate_deploy_args(parser, args)

        config_file_path = generate_config_file()

        cinder_flag = args.install_cinder
        horizon_flag = args.install_horizon
        manila_flag = args.install_manila

        neutron_driver = args.neutron_driver or "ovs"

        enable_cinder_backup = args.enable_cinder_backup

        os_release: str = args.os_release

        if neutron_driver not in ("ovs", "ovn"):
            neutron_driver = "ovs"

        manila_backend = args.manila_backend or "lvm"

        manila_service_instance_auth_method = None

        if manila_backend not in ("generic", "lvm"):
            manila_backend = "lvm"

        manila_share_protocols = (
            args.manila_share_protocols
            or ["nfs"]
        )

        manila_lvm_physical_volume = (
            args.manila_lvm_physical_volume
            if manila_flag == "yes" and args.manila_lvm_physical_volume
            else ""
        )

        cinder_physical_volume = None
        cinder_lvm_size = None

        cinder_enabled_backends = None
        cinder_lvm_volume_group = None

        cinder_nfs_snapshots_enabled = None

        cinder_backup_driver = None
        cinder_backup_compression_algorithm = None
        cinder_backup_file_size_in_bytes = None
        cinder_backup_sha_block_size_in_bytes = None
        cinder_backup_workers = None

        if cinder_flag == "yes":

            cinder_enabled_backends = (
                args.cinder_enabled_backends
                if args.cinder_enabled_backends is not None
                else ["lvm"]
            )

            cinder_lvm_volume_group = (
                args.cinder_volume_group
                if args.cinder_volume_group is not None
                else "cinder-volumes"
            )

            cinder_lvm_size = (
                args.cinder_lvm_image_size_in_gb
                if args.cinder_lvm_image_size_in_gb is not None
                else 5
                )
 
            cinder_physical_volume = args.cinder_physical_volume 

            cinder_nfs_snapshots_enabled = args.enable_nfs_snapshots

        if enable_cinder_backup == "yes":
            cinder_backup_driver = (
                args.cinder_backup_driver
                if args.cinder_backup_driver is not None
                else "posix"
            )

            cinder_backup_compression_algorithm = (
                args.compression_algorithm
                if args.compression_algorithm is not None
                else "zlib"
            )

            cinder_backup_file_size_in_bytes = (
                args.backup_file_size_in_bytes
                if args.backup_file_size_in_bytes is not None
                else 1999994880
            )

            cinder_backup_sha_block_size_in_bytes = (
                args.backup_sha_block_size_in_bytes
                if args.backup_sha_block_size_in_bytes is not None
                else 32768
            )

            cinder_backup_workers = (
                args.backup_workers
                if args.backup_workers is not None
                else 1
            )

        if manila_backend == "generic":
            manila_service_instance_auth_method = (
                args.manila_service_instance_auth_method or "ssh_key"
            )
  
        manila_lvm_vg = (
            args.manila_volume_group
            if manila_flag == "yes" and args.manila_volume_group is not None
            else "manila-shares" if manila_flag == "yes"
            else None
        )

        manila_lvm_size = (
            args.manila_lvm_image_size_in_gb
            if args.manila_lvm_image_size_in_gb is not None
            else 5
        ) if manila_flag == "yes" else 0

        os_config = OpenStackConfig(
            config_file_path=config_file_path,
            install_horizon=parse_bool(horizon_flag),
            install_cinder=parse_bool(cinder_flag),
            install_manila=parse_bool(manila_flag),

            cinder=CinderConfig(
                enabled_backends=cinder_enabled_backends,
                nfs_snapshots_enabled=cinder_nfs_snapshots_enabled,
                lvm_vg=cinder_lvm_volume_group,
                physical_volume=cinder_physical_volume,
                lvm_image_size_in_gb=cinder_lvm_size,
                enable_backup=parse_bool(enable_cinder_backup),

                cinder_backup_params=CinderBackupConfig(
                    compression_algorithm=cinder_backup_compression_algorithm,
                    backup_file_size_in_bytes=cinder_backup_file_size_in_bytes,
                    backup_sha_block_size_in_bytes=cinder_backup_sha_block_size_in_bytes,
                    backup_workers=cinder_backup_workers,
                    backup_driver=cinder_backup_driver,

            ),

            ),
            manila=ManilaConfig(
                lvm_vg=manila_lvm_vg,
                lvm_physical_volume=manila_lvm_physical_volume,
                lvm_image_size_in_gb=manila_lvm_size,
                backend=manila_backend,
                share_protocols=manila_share_protocols,
                dhss_auth_type=manila_service_instance_auth_method,
            ),
            nova_compute=NovaComputeConfig(
                nova_virt_type=args.virt_type,
                cpu_allocation_ratio=args.cpu_allocation_ratio,
                ram_allocation_ratio=args.ram_allocation_ratio,
                disk_allocation_ratio=args.disk_allocation_ratio,
                allow_resize_to_same_host=args.allow_resize_to_same_host,
            ),
            
            neutron_driver=neutron_driver,
            os_mgmt_iface=args.os_management_interface,
            default_gateway=args.default_gateway,
            os_mgmt_gateway=args.os_management_gateway,
            os_release=os_release,
        )

        generate_openstack_config(config=os_config)

        if args.generate_only:
            print(
                f"{colors.GREEN}Configuration file generated in "
                f"'{config_file_path}'{colors.RESET}\n"
            )
            print(
                f"You can start the deployment later with "
                f"'deploystack deploy --config-file {config_file_path}'"
            )
            sys.exit(0)

        start_deployment(config_file_path, config_generated=True)

    else:

        if args.config_file is None or not os.path.exists(args.config_file):
            print(
                f"{colors.RED}Configuration file not found. "
                f"Generate it first using "
                f"'deploystack generate-config <file>' "
                f"or 'deploystack deploy -aio <arguments> --generate-only'"
                f"{colors.RESET}"
            )
            sys.exit(1)

        start_deployment(args.config_file, config_generated=False)