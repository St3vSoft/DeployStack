
from ..utils.config import Config
from ..utils.resources.loopback import Loopback
from ..utils.resources.filter import LVMFilter

def build_stop_parser(subparsers):

    parser = subparsers.add_parser(
        "stop",
        help="Stop a loopback resource"
    )

    parser.add_argument(
        "resource",
        choices=["cinder", "manila", "all"],
        default="all",
        help="Resource to stop"
    )

    parser.add_argument(
        "backend",
        help="Backend Loopback to start"
    )

    parser.set_defaults(func=stop)

    return parser

def stop(args):

    config = Config()

    for resource_name, backend_name, backend_config in (
        config.resolve_backends(args.resource, args.backend)
    ):
        resource = Loopback(backend_config)

        resource.deactivate()
        resource.detach()

        print(
            f"Powered off {resource_name}/{backend_name}"
        )