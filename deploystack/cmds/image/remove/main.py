import sys

from ....utils.tasks.check_deployment import is_openstack_ready
from .runner import remove_image

def init_parser(subparsers):

    parser = subparsers.add_parser(
        "remove",
        help="Delete an existing image in the cloud"
    )

    parser.add_argument(
        "--image",
        dest="image",
        help="Glance Image Name or ID"
    )

    parser.add_argument(
        "--timeout",
        default=300,
        dest="timeout",
        type=int,
        help="Maximum time to wait to check if the image has been deleted in OpenStack (default: 300s)"
    )

def remove(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        parser.exit(1)

    if not is_openstack_ready():
        sys.exit(1)

    remove_image(args.image, args.timeout)

   