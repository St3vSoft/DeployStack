import argparse
import sys

from ..utils.core import colors

class ColoredArgumentParser(argparse.ArgumentParser):

    def print_help_error(self, message, parser_name: str):
        for action in self._actions:
            if isinstance(action, argparse._SubParsersAction):
                cmd_parser = action.choices.get(parser_name)

                if cmd_parser is not None:
                    print(f"{colors.RED}Error: {message}{colors.RESET}\n")
                    cmd_parser.print_help()
                    self.exit(2)
    
    def error(self, message):
        argv = sys.argv[1:]

        if not argv:
            return super().error(message)

        if not argv or argv[0].startswith("-") or argv[0] not in ("deploy", "launch", "generate-config", "image", "volume"):
            self.print_help()
            print(f"\n{colors.RED}Error: {message}{colors.RESET}")
            self.exit(2)

        command = argv[0]

        self.print_help_error(message, command)
        super().error(message)