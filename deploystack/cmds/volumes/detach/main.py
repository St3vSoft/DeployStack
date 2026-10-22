import sys

from .runner import detach as detach_volume

from ....utils.tasks.check_deployment import is_openstack_ready, is_cinder_available

def init_parser(subparsers):

    parser = subparsers.add_parser(
        "detach",
        help="Detach a volume from an instance"
    )

    parser.add_argument(
        "--volume",
        required=True,
        help="ID or name of the volume to detach."
    )

    parser.add_argument(
        "--instance",
        required=True,
        help="ID or name of the instance from which to detach the volume."
    )

def detach(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        parser.exit(1)

    if not is_openstack_ready():
        sys.exit(1)

    if not is_cinder_available():
        sys.exit(1)

    detach_volume(
        args.volume,
        args.instance
    )

