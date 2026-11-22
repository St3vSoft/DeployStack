import uuid
import sys

from ...utils.tasks.check_deployment import is_openstack_ready, is_cinder_available
from .runner import launch as launch_instance

from ...utils.core import colors

def init_parser(parser): 

    general_options = parser.add_argument_group("General Options")
    volume_options = parser.add_argument_group("Volume Options")

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

    volume_options.add_argument("--boot-from-volume", action="store_true", help="Boot the instance from a volume created from the specified image")
    volume_options.add_argument("--keep-on-termination", action="store_true", help="Keep the volume after the instance is deleted")
    volume_options.add_argument("--volume-size-in-gb", type=int, help="Size of the root volume in GB")
    
def launch(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        print(f"\nTip: Run '{colors.BRIGHT_BLUE}deploystack launch --help{colors.RESET}' for detailed usage of each argument.")
        sys.exit(1)

    boot_from_volume = getattr(args, "boot_from_volume", False)
    keep_on_termination = getattr(args, "keep_on_termination", False)
    volume_size_in_gb = getattr(args, "volume_size_in_gb", None)

    if boot_from_volume and not is_cinder_available():
        parser.error("Boot from volume requires Cinder to be available.")

    if volume_size_in_gb is not None:
        if not boot_from_volume:
            parser.error("--volume-size-in-gb requires --boot-from-volume.")
        if volume_size_in_gb <= 0:
            parser.error("--volume-size-in-gb must be greater than 0.")

    if keep_on_termination and not boot_from_volume:
        parser.error("--keep-on-termination requires --boot-from-volume.")
            
    if not is_openstack_ready():
        sys.exit(1)

    launch_instance(
        name=args.name,
        image=args.image,
        flavor=args.flavor,
        network=args.network,
        keypair=args.keypair,
        password=args.password,
        timeout=args.timeout,
        boot_from_volume=boot_from_volume,
        volume_size_in_gb=volume_size_in_gb,
        keep_volume_on_termination=keep_on_termination
    )