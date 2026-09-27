import subprocess

from ..utils.config import Config
from ..utils.resources.loopback import Loopback

def build_attach_subparser(subparsers):

    parser = subparsers.add_parser(
        "attach"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila", "all"],
        default="all"
    )

    parser.set_defaults(func=attach)

    return parser

def attach(args):

    config = Config()

    for backend_name, backend_config in config.backends(args.resource).items():

        resource = Loopback(backend_config)
        loop_dev = resource.attach()

        print(
            f"Attached {args.resource}/{backend_name}: "
            f"{loop_dev}"
        )
