from ..utils.config import Config
from ..utils.resources.loopback import Loopback

from ..utils import colors


def print_status(name, status):

    image_exists = (
        f"{colors.GREEN}yes{colors.RESET}"
        if status["image_exists"]
        else f"{colors.RED}no{colors.RESET}"
    )

    attached = (
        f"{colors.GREEN}yes{colors.RESET}"
        if status["attached"]
        else f"{colors.RED}no{colors.RESET}"
    )

    loop_device = (
        f"{colors.GREEN}{status['loop_device']}{colors.RESET}"
        if status["loop_device"]
        else f"{colors.RED}-{colors.RESET}"
    )

    print(f"Resource: {name}")
    print(f"  Image: {status['image']}")
    print(f"  Image exists: {image_exists}")
    print(f"  Attached: {attached}")
    print(f"  Loop device: {loop_device}")


def build_check_parser(subparsers):

    parser = subparsers.add_parser(
        "check",
        help="Check loopback resources"
    )

    parser.add_argument(
        "resource",
        nargs="?",
        choices=["cinder", "manila"],
        default=None,
        help="Resource to check"
    )

    parser.add_argument(
        "backend",
        nargs="?",
        default=None,
        help="Backend to check"
    )

    parser.set_defaults(func=check)

    return parser


def check(args):

    config = Config()

    for resource_name, backend_name, backend_config in (
        config.resolve_backends(args.resource, args.backend)
    ):
        resource = Loopback(backend_config)
        status = resource.check()

        print_status(
            f"{resource_name}/{backend_name}",
            status,
        )
