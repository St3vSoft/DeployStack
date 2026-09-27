from ..utils.config import Config
from ..utils.resources.loopback import Loopback

def build_detach_parser(subparsers):
    parser = subparsers.add_parser(
        "detach",
        help="Detach a loopback resource"
    )

    parser.add_argument(
        "resource",
        choices=["cinder", "manila"],
        help="Resource to detach"
    )

    parser.add_argument(
        "backend",
        nargs="?",
        default=None,
        help="Backend Loopback to detach"
    )

    parser.set_defaults(func=detach)

    return parser

def detach(args):

    config = Config()

    for resource_name, backend_name, backend_config in (
        config.resolve_backends(args.resource, args.backend)
    ):
        resource = Loopback(backend_config)

        resource.detach()

        print(
            f"Detached {resource_name}/{backend_name}"
        )
