import sys

from .create.main import init_parser as create_init_parser
from .attach.main import init_parser as attach_init_parser
from .detach.main import init_parser as detach_init_parser
from .remove.main import init_parser as remove_init_parser

from .detach.runner import reset_volume_state
from .detach.runner import is_uuid, get_volume_id_from_name

def init_parser(subparsers):

    volume_parser = subparsers.add_parser(
        name="volume",
        help="Manage volumes"
    )

    volume_subparsers = volume_parser.add_subparsers(
        dest="volume_cmd",
        metavar="<command>",
        required=False
    )

    volume_parser.add_argument(
        "--reset-status",
        dest="reset_status",
        help="Volume Name or ID"
    )

    create_init_parser(volume_subparsers)
    attach_init_parser(volume_subparsers)
    detach_init_parser(volume_subparsers)
    remove_init_parser(volume_subparsers)

def volume(parser, args) -> None:
    
    if args.reset_status:
       volume_id = volume if is_uuid(args.reset_status) else get_volume_id_from_name(args.reset_status)
       
       print(f"Resetting volume '{volume_id}' status ...\n")
       reset_volume_state(volume_id)
       sys.exit(0)

    if args.volume_cmd == "create":
        from .create.main import create
        create(parser, args)
    elif args.volume_cmd == "attach":
        from .attach.main import attach
        attach(parser, args)
    elif args.volume_cmd == "detach":
        from .detach.main import detach
        detach(parser, args)
    elif args.volume_cmd == "remove":
        from .remove.main import remove
        remove(parser, args)



