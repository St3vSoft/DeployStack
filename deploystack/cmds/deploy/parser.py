import argparse
import sys

from ...cli.parser import MainArgumentParser

class DeployArgumentParser(MainArgumentParser):

    def error(self, message):
        if self.prog.endswith(" deploy"):
            self.print_help()
            self.exit(2, f"\nError: {message}\n")

        super().error(message)