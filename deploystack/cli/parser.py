import argparse
import sys

from ..utils.core import colors

class ColoredArgumentParser(argparse.ArgumentParser):
    
    def error(self, message):
        if self.prog.endswith(" deploy"):
            self.print_help()
            self.exit(2, f"\nError: {message}\n")

        super().error(message)