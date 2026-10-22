import sys

from .runner import remove as remove_volume

from ....utils.tasks.check_deployment import is_openstack_ready, is_cinder_available

def init_parser(subparsers):

    parser = subparsers.add_parser(
        "remove",
        help="Remove a existing volume from Cinder"
    )

    parser.add_argument(
        "--volume",
        dest="volume",
        help="Volume Name or ID"
    )

    parser.add_argument(
        "--timeout",
        default=300,
        dest="timeout",
        type=int,
        help="Maximum time to wait to check if the volume has been deleted in OpenStack (default: 300s)"
    )

def remove(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        parser.exit(1)

    if not is_openstack_ready():
        sys.exit(1)

    if not is_cinder_available():
        sys.exit(1)

    remove_volume(args.volume, args.timeout)


