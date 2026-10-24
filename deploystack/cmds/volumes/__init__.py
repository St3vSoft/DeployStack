import sys

from .create.main import init_parser as create_init_parser
from .attach.main import init_parser as attach_init_parser
from .detach.main import init_parser as detach_init_parser
from .remove.main import init_parser as remove_init_parser
from .reset.main import init_parser as reset_init_parser

from .create.main import create as run_create
from .attach.main import attach as run_attach
from .detach.main import detach as run_detach
from .remove.main import remove as run_remove
from .reset.main import reset as run_reset

from ...utils.core import colors

def init_parser(parser):
    create_init_parser(parser)
    attach_init_parser(parser)
    detach_init_parser(parser)
    remove_init_parser(parser)
    reset_init_parser(parser)

def volumes(parser, args) -> None:

    match args.volume_cmd:
        case "create":
            run_create(parser, args)
        case "attach":
            run_attach(parser, args)
        case "detach":
            run_detach(parser, args)
        case "remove":
            run_remove(parser, args)
        case "reset":
            run_reset(parser, args)
        case None:
            print(f"{colors.YELLOW}No command provided. Available commands:{colors.RESET}\n")
            parser.print_help()
            print(f"\nTip: Run '{colors.BRIGHT_BLUE}deploystack volume --help{colors.RESET}' for detailed usage of each command.")
            sys.exit(1)


