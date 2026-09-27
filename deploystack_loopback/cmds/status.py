from .check import print_status

from ..utils.config import Config
from ..utils.resources.loopback import Loopback

def build_status_parser(subparsers):

    parser = subparsers.add_parser(
        "status",
        help="Show loopback resources status"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila"],
        default=None,
        help="Resource to show"
    )

    parser.add_argument(
        "backend",
        nargs="?",
        default=None,
        help="Backend Loopback to show"
    )

    parser.set_defaults(func=status)

    return parser

def status(args):
    config = Config()

    for resource_name, backend_name, backend_config in (
        config.resolve_backends(args.resource, args.backend)
    ):
        resource = Loopback(backend_config)

        print_status(
            f"{resource_name}/{backend_name}",
            resource.check(),
        )
