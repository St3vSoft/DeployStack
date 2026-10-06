import sys

from ....utils.tasks.check_deployment import is_openstack_ready

from .runner import upload_image

def init_parser(subparsers):

    parser = subparsers.add_parser(
        "upload",
        help="Upload a new, ready-made cloud image into Glance from the web"
    )

    parser.add_argument(
        "--image-name",
        dest="image_name",
        help="Custom image name (if not provided, a default name will be used)"
    )

    parser.add_argument(
        "--arch",
        choices=["amd64", "arm64", "x86_64", "aarch64"],
        default="amd64",
        help="CPU architecture of the image (default: amd64)"
    )

    parser.add_argument(
        "--os",
        required=True,
        help="OS name of the cloud image to upload"
    )

    parser.add_argument(
        "--version",
        required=True,
        help="OS version of the cloud image to upload"
    )

    parser.add_argument(
        "--visibility",
        choices=["public", "private", "shared", "community"],
        default="public",
        help="Visibility of the image in Glance (default: public)"
    )

    parser.add_argument(
        "--output-dir",
        default="/tmp",
        dest="output_dir",
        help="Directory where the image will be downloaded before upload (default: /tmp)"
    )

    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the downloaded image file after upload instead of deleting it"
    )

    parser.add_argument(
        "--timeout",
        default=300,
        dest="timeout",
        type=int,
        help="Maximum time in seconds to wait for the uploaded image to become ACTIVE in OpenStack (default: 300s)"
    )

def upload(parser, args) -> None:

    if args.command is None:
        parser.print_help()
        parser.exit(1)

    if not is_openstack_ready():
        sys.exit(1)

    upload_image(
        args.os,
        args.image_name,
        args.version,
        args.visibility,
        args.output_dir,
        args.keep,
        args.arch,
        args.timeout
    )
