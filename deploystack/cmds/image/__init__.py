import sys

from .upload.main import init_parser as upload_init_parser
from .remove.main import init_parser as remove_init_parser

from .upload.main import upload as run_upload
from .remove.main import remove as run_remove

from ...utils.core import colors

def init_parser(parser):

    upload_init_parser(parser)
    remove_init_parser(parser)

def images(parser, args) -> None:

    match args.command:
        case "upload":
            run_upload(parser, args)
        case "remove":
            run_remove(parser, args)
        case None:
            print(f"{colors.YELLOW}No command provided. Available commands:{colors.RESET}\n")
            parser.print_help()
            print(f"\nTip: Run '{colors.BRIGHT_BLUE}deploystack image --help{colors.RESET}' for detailed usage of each command.")
            sys.exit(1)