import sys

from .runner import reset as reset_volume

from ....utils.tasks.check_deployment import is_openstack_ready, is_cinder_installed

def init_parser(subparsers):

    parser = subparsers.add_parser(
        "reset",
        help="Reset a existing volume state from Cinder"
    )

    parser.add_argument(
        "--volume",
        dest="volume",
        required=True,
        help="Volume Name or ID"
    )

def reset(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        parser.exit(1)

    if not is_openstack_ready():
        sys.exit(1)

    if not is_cinder_installed():
        sys.exit(1)

    reset_volume(args.volume)


