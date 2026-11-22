import uuid
import sys

from ...utils.tasks.check_deployment import is_openstack_ready, is_cinder_available
from .runner import launch as launch_instance

from ...utils.core import colors

def init_parser(parser): 

    general_options = parser.add_argument_group("General Options")

    general_options.add_argument(
        "--name",
        default=f"instance-{uuid.uuid4().hex[:8]}",
        help="Name of the instance to launch. Defaults to a random generic instance name."
        )
    
    general_options.add_argument(
        "--image",
        default="cirros",
        help="Name of the image to use for the instance. Defaults to 'cirros'."
    )

    general_options.add_argument(
        "--flavor",
        default="m1.tiny",
        help="Flavor (size) of the instance. Defaults to 'm1.tiny'."
    )

    general_options.add_argument(
        "--network",
        default="internal",
        help="Network to attach the instance to. Defaults to 'internal'."
    )

    general_options.add_argument(
        "--keypair",
        default="",
        help="Existing key pair in OpenStack to associate with the instance"
    )

    general_options.add_argument(
        "--password",
        default="",
        help="Password for the admin instance user."
    )

    general_options.add_argument(
        "--timeout",
        default=100,
        type=int,
        help="Maximum time to wait for the operation to complete, in seconds (default: 100)."
    )

    if is_cinder_available():
        volume_options = parser.add_argument_group("Volume Options")

        volume_options.add_argument("--boot-from-volume", action="store_true", help="Boot the image from a volume")
        volume_options.add_argument("--volume-size-in-gb", type=int, help="Size of the root volume in GB")
    
def launch(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        print(f"\nTip: Run '{colors.BRIGHT_BLUE}deploystack launch --help{colors.RESET}' for detailed usage of each argument.")
        sys.exit(1)
    elif args.volume_size_in_gb and not args.boot_from_volume:
        parser.error("The --volume-size-in-gb flag requires the --boot-from-volume flag.")

    if not is_openstack_ready():
        sys.exit(1)

    launch_instance(name=args.name, image=args.image, flavor=args.flavor, network=args.network, keypair=args.keypair, password=args.password, timeout=args.timeout)
