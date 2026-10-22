import argparse
import sys

from ..utils.core import colors

class ColoredArgumentParser(argparse.ArgumentParser):
    
    def error(self, message):
        print(f"{colors.RED}Error: {message}{colors.RESET}\n")
        self.print_help()
        sys.exit(2)