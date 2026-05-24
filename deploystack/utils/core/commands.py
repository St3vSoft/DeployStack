import subprocess
from .spinner import Spinner
from ...utils.core import colors

from ..core.system_utils import build_openstack_env

import time
import sys

OPENSTACK_ENV = None

def init_openstack_context(config):
    global OPENSTACK_ENV
    OPENSTACK_ENV = build_openstack_env(config)

def run_command_output(cmd, ignore_errors=False, env=None):

    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if ignore_errors:
            return e.stdout.strip() if e.stdout else ""
        else:
            raise


def run_command_sync(command):
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False


def run_command(cmd, message="", ignore_errors=False, ignore_exit_codes=None, retries=0, delay=1, env=None):
    attempt = 0
    spinner = Spinner(message)
    spinner.start()

    while attempt <= retries:
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )

            output_lines = []
            for line in iter(process.stdout.readline, ''):
                line = line.rstrip('\n')
                if line:
                    output_lines.append(line)

            process.wait()
            returncode = process.returncode

            if ignore_exit_codes and returncode in ignore_exit_codes:
                spinner.stop("WARNING", color="green", width=50)
                return True

            if returncode == 0:
                spinner.stop("DONE", color="yellow", width=50)
                return True

            # Failed: retry?
            if attempt < retries:
                spinner.stop("RETRY", color="yellow", width=50)
                time.sleep(delay)
                attempt += 1
                spinner = Spinner(message)
                spinner.start()
                continue

            # Print output only on error
            if ignore_errors:
                spinner.stop("WARNING", color="green", width=50)
                print(f"{colors.GREEN}Command '{' '.join(cmd)}' failed with exit code {returncode} but ignored as non-critical{colors.RESET}")
                return True
            else:
                spinner.stop("ERROR", color="red", width=50)
                print(f"\n{colors.RED}Execution of: '{' '.join(cmd)}' returned exit code {returncode}{colors.RESET}")
                if output_lines:
                    print("\nCommand Last Output:")
                    print("\n".join(output_lines))
                return False

        except Exception as e:
            spinner.stop("ERROR", color="red", width=50)
            print(f"{colors.RED}Exception running command: {e}{colors.RESET}")
            return False

    spinner.stop("FAILED", color="red", width=50)
    sys.exit(1)


def run_sync_command_with_retry(command, max_retries=3, interval=1):
    for attempt in range(max_retries):
        success = run_command_sync(command)

        if success:
            return True

        if attempt < max_retries - 1:
            time.sleep(interval)

    sys.exit(1)
    return False

def os_run(cmd, text=None):
    return run_command(cmd, text=text, env=OPENSTACK_ENV)

def os_run_output(cmd):
    return run_command_output(cmd, env=OPENSTACK_ENV)