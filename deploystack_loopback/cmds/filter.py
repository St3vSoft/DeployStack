from ..utils.config import Config

from ..utils.resources.loopback import Loopback
from ..utils.resources.filter import LVMFilter

from ..utils.colors import GREEN, RESET, RED

def print_filter(devices):

    print("LVM device filter")

    for device in devices:
        print(
            f"  {GREEN}{device}{RESET}    allowed"
        )

    print(
        f"  {RED}*{RESET}              rejected"
    )

def build_filter_parser(subparsers):

    parser = subparsers.add_parser(
        "filter",
        help="Manage LVM device filter"
    )

    filter_subparsers = parser.add_subparsers(
        dest="filter_command",
        required=True
    )

    show_parser = filter_subparsers.add_parser(
        "show",
        help="Show current LVM filter"
    )
    show_parser.set_defaults(func=cmd_filter_show)

    # filter rebuild
    rebuild_parser = filter_subparsers.add_parser(
        "rebuild",
        help="Rebuild LVM filter"
    )
    rebuild_parser.set_defaults(func=cmd_filter_rebuild)

    # filter add
    add_parser = filter_subparsers.add_parser(
        "add",
        help="Add device to LVM filter"
    )
    add_parser.add_argument(
        "device",
        help="Loop device, e.g. /dev/loopX"
    )
    add_parser.set_defaults(func=cmd_filter_add)

    # filter remove
    remove_parser = filter_subparsers.add_parser(
        "remove",
        help="Remove device from LVM filter"
    )
    remove_parser.add_argument(
        "device",
        help="Loop device, e.g. /dev/loopX"
    )
    remove_parser.set_defaults(func=cmd_filter_remove)

    return parser

def cmd_filter_show(args):
    config = Config()

    lvm_filter = LVMFilter(config.lvm_config)
    devices = lvm_filter.show()

    print_filter(devices)

def cmd_filter_rebuild(args):

    config = Config()

    resources = [
        Loopback(backend_config)
        for _, _, backend_config in config.resolve_backends()
    ]

    lvm_filter = LVMFilter(config.lvm_config)
    lvm_filter.rebuild(resources)

def cmd_filter_add(args):
    config = Config()

    lvm_filter = LVMFilter(config.lvm_config)

    if lvm_filter.add(args.device):
        print(f"Added: {args.device}")
    else:
        print(f"Already present: {args.device}")

def cmd_filter_remove(args):
    config = Config()
    
    lvm_filter = LVMFilter(config.lvm_config)

    if lvm_filter.remove(args.device):
        print(f"Removed: {args.device}")
    else:
        print(f"Not present: {args.device}")