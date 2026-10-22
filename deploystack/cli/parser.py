import argparse
import sys

from ..utils.core import colors

class MainArgumentParser(argparse.ArgumentParser):

    def print_help_error(self, message, parser_path: tuple[str, ...]):
        parser = self

        for name in parser_path:
            found = None

            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    found = action.choices.get(name)
                    if found is not None:
                        break

            if found is None:
                break

            parser = found

        print(f"{colors.RED}Error: {message}{colors.RESET}\n")
        parser.print_help()
        self.exit(2) 
    
    def error(self, message):
        argv = sys.argv[1:]

        commands = (
            "deploy",
            "launch",
            "generate-config",
            "image",
            "volume",
        )

        if not argv or argv[0].startswith("-") or argv[0] not in commands:
            print(f"{colors.RED}Error: {message}{colors.RESET}\n")
            self.print_help()
            self.exit(2)

        command = argv[0]

        if command == "image" and len(argv) > 1:
            image_subcommand = argv[1]

            if image_subcommand in ("upload", "remove"):
                self.print_help_error(message, ("image", image_subcommand),)
                return

        elif command == "volume" and len(argv) > 1:
            volume_subcommand = argv[1]

            if volume_subcommand in ("create", "attach", "detach", "remove", "reset"):
                self.print_help_error(message, ("volume", volume_subcommand),)
                return

        self.print_help_error(message, (command,))