import sys

from .runner import attach as attach_volume

from ....utils.tasks.check_deployment import is_openstack_ready, is_cinder_available

def init_parser(subparsers):

    parser = subparsers.add_parser(
        "attach",
        help="Attach a volume to an instance"
    )

    parser.add_argument(
        "--volume",
        required=True,
        help="ID or name of the volume to attach."
    )

    parser.add_argument(
        "--instance",
        required=True,
        help="ID or name of the instance to attach the volume to."
    )

def attach(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        parser.exit(1)

    if not is_openstack_ready():
        sys.exit(1)

    if not is_cinder_available():
        sys.exit(1)

    attach_volume(
        args.volume,
        args.instance
    )

    

        