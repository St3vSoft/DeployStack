import sys
import uuid

from .runner import create as create_volume

from ....utils.tasks.check_deployment import is_openstack_ready, is_cinder_installed

def init_parser(subparsers):

    parser = subparsers.add_parser(
        "create",
        help="Create a new volume"
    )

    source_group = parser.add_mutually_exclusive_group(required=False)

    parser.add_argument(
        "--name",
        default=f"volume-{uuid.uuid4().hex[:8]}",
        help="The name of the volume to create"
    )

    parser.add_argument(
        "--size",
        default=5,
        help="The size of the volume in GB (default: 5 GB)"
    )

    source_group.add_argument(
        "--is-bootable",
        action="store_true",
        help="Mark the volume as bootable. Use this flag if the volume should be usable as a boot disk."
    )

    source_group.add_argument(
        "--image",
        help="Optional Glance image ID or name to create the volume from."
    )

    source_group.add_argument(
        "--backup",
        help="Optional Cinder Volume Backup ID or name to create the volume from."
    )

    source_group.add_argument(
        "--snapshot",
        help="Optional Cinder Volume Snapshot ID or name to create the volume from."
    )

    parser.add_argument(
        "--timeout",
        default=300,
        dest="timeout",
        type=int,
        help="Maximum time in seconds to wait for the volume to become ACTIVE in OpenStack (default: 300s)"
    )

def create(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        parser.exit(1)

    if not is_openstack_ready():
        sys.exit(1)

    if not is_cinder_installed():
        sys.exit(1)

    create_volume(
        args.name,
        args.size,
        args.is_bootable,
        args.image,
        args.backup,
        args.snapshot,
        args.timeout
    )


        