import os
import sys

from .utils.core import colors
from .cli.builder import build_main_parser, build_deploy_parser, build_launch_parser, build_generate_config_parser, build_images_parser, build_volumes_parser

from .cmds.deploy.main import deploy as run_deploy
from .cmds.launch.main import launch as run_launch
from .cmds.generate_config import generate_config as run_generate_config
from .cmds.image import images as run_images
from .cmds.volumes import volumes as run_volumes

def print_banner():
    print(f"{colors.BRIGHT_BLUE}Welcome to DeployStack Utility{colors.RESET}\n")

def main():
    print_banner()

    if os.geteuid() != 0:
        print(f"{colors.RED}This utility must be run as root.{colors.RESET}")
        print(f"{colors.YELLOW}Try: sudo <command>{colors.RESET}\n")
        sys.exit(1)

    main_parser, subparsers = build_main_parser()

    command_parsers = {
        "deploy": build_deploy_parser(subparsers),
        "launch": build_launch_parser(subparsers),
        "generate-config": build_generate_config_parser(subparsers),
        "image": build_images_parser(subparsers),
        "volume": build_volumes_parser(subparsers),
    }
    
    # Only parse known args to avoid automatic error exit
    main_args = main_parser.parse_args()

    command_parser = command_parsers[main_args.command]

    match main_args.command:
        case "deploy":
            run_deploy(command_parser, main_args)

        case "launch":
            run_launch(command_parser, main_args)

        case "generate-config":
            run_generate_config(command_parser, main_args)

        case "image":
            run_images(command_parser, main_args)

        case "volume":
            run_volumes(command_parser, main_args)

        case None:
            print(f"{colors.YELLOW}No command provided. Available commands:{colors.RESET}\n")
            main_parser.print_help()
            print(f"\nTip: Run '{colors.BRIGHT_BLUE}deploystack <command> --help{colors.RESET}' for detailed usage of each command.")
            sys.exit(1)