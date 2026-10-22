import argparse
import shutil
import os

from ...utils.core import colors
from ...templates import OPENSTACK_CONFIG_TEMPLATE

def init_parser(parser): 
    parser.add_argument("file", help="Path to configuration file")

def generate_config(parser, args) -> None:
    """
    Generate a template configuration file for OpenStack deployment.
    """

    dst_file = args.file
    dst_dir = os.path.dirname(dst_file)

    try:
        if dst_dir:
            os.makedirs(dst_dir, exist_ok=True)

        shutil.copy(OPENSTACK_CONFIG_TEMPLATE, dst_file)

    except PermissionError:
        print(f"{colors.RED}Error: Permission denied when creating '{dst_file}'. Try running with sudo.{colors.RESET}")
        return
    except FileNotFoundError:
        print(f"{colors.RED}Error: Template file '{OPENSTACK_CONFIG_TEMPLATE}' not found.{colors.RESET}")
        return
    except Exception as e:
        print(f"{colors.RED}Unexpected error: {e}{colors.RESET}")
        return

    print(f"{colors.GREEN}Configuration file successfully generated!{colors.RESET}\n")
    print(f"Path: {colors.BRIGHT_BLUE}{dst_file}{colors.RESET}")
    print("\nTip: You can now edit this file to customize your OpenStack deployment before running 'deploystack deploy'.")