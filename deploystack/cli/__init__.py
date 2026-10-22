import argparse

from typing import Any

from .parser import ColoredArgumentParser

from ..utils.core import colors

from ..cmds.deploy.main import init_parser as build_deploy_subparser
from ..cmds.launch.main import init_parser as build_launch_subparser
from ..cmds.generate_config import init_parser as build_generate_config_subparser

from ..cmds.image import init_parser as build_image_upload_subparser

from ..cmds.volumes import init_parser as build_volume_subparser

def build_deploy_parser(main_subparsers: argparse.ArgumentParser_SubParsersAction) -> ColoredArgumentParser:

    deploy_parser = main_subparsers.add_parser("deploy",  help="Start the OpenStack Deployment on the current node")

    build_deploy_subparser(deploy_parser)

    return deploy_parser

def build_launch_parser(main_subparsers: argparse.ArgumentParser_SubParsersAction) -> ColoredArgumentParser:

    launch_parser = main_subparsers.add_parser("launch", help="Launch an OpenStack instance")

    build_launch_subparser(launch_parser)

    return launch_parser

def build_generate_config_parser(main_subparsers: argparse.ArgumentParser_SubParsersAction) -> ColoredArgumentParser:

    generate_config_parser = main_subparsers.add_parser("generate-config", help="Generate a template configuration file")

    build_generate_config_subparser(generate_config_parser)

    return generate_config_parser

def build_images_parser(main_subparsers: argparse.ArgumentParser_SubParsersAction) -> ColoredArgumentParser:

    image_parser = main_subparsers.add_parser("image", help="Manage cloud images")
    image_subparsers = image_parser.add_subparsers(dest="image_cmd", metavar="<command>", required=True)

    build_image_upload_subparser(image_subparsers)

    return image_subparsers

def build_volumes_parser(main_subparsers: argparse.ArgumentParser_SubParsersAction) -> ColoredArgumentParser:

    volume_parser = main_subparsers.add_parser(name="volume", help="Manage volumes")
    volume_subparsers = volume_parser.add_subparsers(dest="volume_cmd", metavar="<command>", required=True)

    build_volume_subparser(volume_subparsers)

    return volume_subparsers

def build_main_parser() -> tuple[ColoredArgumentParser, Any]:

    max_cmd_len = max(len(c) for c in cmds.keys())

    parser = ColoredArgumentParser(
        description=(
            "DeployStack - OpenStack deployment and management utility"
        ),
        epilog=(
            "\nExamples:\n"
            "  Deploy a single-node OpenStack environment:\n"
            f"    {colors.BRIGHT_BLUE}deploystack deploy --allinone{colors.RESET}\n\n"
            "  Generate a configuration file:\n"
            f"    {colors.BRIGHT_BLUE}deploystack generate-config config.yaml{colors.RESET}\n\n"
            "  Launch an instance:\n"
            f"    {colors.BRIGHT_BLUE}deploystack launch --help{colors.RESET}"
        ),
        formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(
            prog,
            max_help_position=max_cmd_len + 20,
            width=150
        ),
    )

    subparsers = parser.add_subparsers(
        title="Commands",
        dest="command",
        metavar="",
        required=True,
        parser_class=ColoredArgumentParser,
    )

    return parser, subparsers