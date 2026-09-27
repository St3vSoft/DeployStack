from ..utils.config import Config

from ..utils.resources.loopback import Loopback
from ..utils.resources.filter import LVMFilter

def build_reconcile_parser(subparsers):

    parser = subparsers.add_parser(
        "reconcile",
        help="Reconcile loopback resources and LVM state"
    )

    parser.set_defaults(func=reconcile)

    return parser

def reconcile(args):

    config = Config()
    resources = []

    for resource_name, backend_name, backend_config in (
        config.resolve_backends()
    ):
        resource = Loopback(backend_config)

        if not resource.image.exists():
            continue

        loop_dev = resource.attach()

        resources.append(resource)

        print(
            f"Reconciled {resource_name}/{backend_name}: "
            f"{loop_dev}"
        )

    lvm_filter = LVMFilter(config.lvm_config)
    lvm_filter.rebuild(resources)

    for resource in resources:
        resource.scan()
        resource.activate()
