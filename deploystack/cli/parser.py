import argparse
import sys

from ..utils.core import colors

class ColoredArgumentParser(argparse.ArgumentParser):
    
    def error(self, message):

        argv = sys.argv[1:]

        if "deploy" in argv:
            for action in self._actions:
                if isinstance(action ,argparse._SubParsersAction):
                    deploy_parser = action.choices.get("deploy")

                    if deploy_parser is not None:
                        print(f"\n{colors.RED}Error: {message}{colors.RESET}\n")
                        deploy_parser.print_help()
                        self.exit(2)

        super().error(message)