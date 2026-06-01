import subprocess
from .spinner import Spinner
from ...utils.core import colors

from ..core.system_utils import build_openstack_env

import time
import sys

def init_openstack_context(config):
    global OPENSTACK_ENV
    OPENSTACK_ENV = build_openstack_env(config)

def run_command_output(cmd, ignore_errors=False, env=None):
    result = subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    return result.stdout.strip()

def run_command_sync(command, env=None):
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        return True
    except subprocess.CalledProcessError:
        return False

def run_commands(steps, message=None, env=None):
    spinner = Spinner(message) if message else None
    if spinner:
        spinner.start()

    for step in steps:
        if isinstance(step[0], list):
            cmd = step[0]
            kwargs = step[1] if len(step) > 1 and isinstance(step[1], dict) else {}
        else:
            cmd = step
            kwargs = {}

        ignore_errors = kwargs.get("ignore_errors", False)
        res = {}

        ok = run_command(cmd, message="", env=env, ignore_errors=ignore_errors, silent=True, context=res)

        if not ok and not ignore_errors:
            if spinner:
                spinner.stop("ERROR", color="red", width=50)
                
                output_lines = res.get("output", "").splitlines()

                print(f"\n{colors.RED}Execution of: '{' '.join(res.cmd)}' returned exit code {res.returncode}{colors.RESET}")
                if output_lines:
                    print("\nLast output:")
                    print("\n".join(output_lines))
                    print()
            return False

    if spinner:
        spinner.stop("DONE", color="yellow", width=50)

    return True

def run_command(
    cmd,
    message="",
    ignore_errors=False,
    ignore_exit_codes=None,
    retries=0,
    delay=1,
    env=None,
    timeout=120,
    silent=False,
    context=None
):
    attempt = 0
    spinner = Spinner(message) if message else None

    if spinner:
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

            try:
                output, _ = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                output, _ = process.communicate()

                if attempt < retries:
                    attempt += 1
                    if spinner:
                        spinner.stop("TIMEOUT RETRY", color="yellow", width=50)
                    time.sleep(delay)
                    if spinner:
                        spinner.start()
                    continue

                if spinner:
                    spinner.stop("TIMEOUT", color="red", width=50)

                print(f"{colors.RED}Timeout running: {' '.join(cmd)}{colors.RESET}")
                return False

            returncode = process.returncode
            output_lines = output.splitlines() if output else []

            if ignore_exit_codes and returncode in ignore_exit_codes:
                if spinner:
                    spinner.stop("WARNING", color="green", width=50)
                return True

            if returncode == 0:
                if spinner:
                    spinner.stop("DONE", color="yellow", width=50)
                return True

            # retry
            if attempt < retries:
                attempt += 1
                if spinner:
                    spinner.stop("RETRY", color="yellow", width=50)
                time.sleep(delay)
                if spinner:
                    spinner.start()
                continue

            # error output
            if ignore_errors:
                if spinner:
                    spinner.stop("WARNING", color="green", width=50)
                print(
                    f"{colors.GREEN}Command failed (ignored): "
                    f"{' '.join(cmd)}{colors.RESET}"
                )
                return True

            if spinner:
                spinner.stop("ERROR", color="red", width=50)

            if not silent:
                print(f"\n{colors.RED}Execution of: '{' '.join(cmd)}' returned exit code {returncode}{colors.RESET}")
                if output_lines:
                    print("\nLast output:")
                    print("\n".join(output_lines))
                    print()

            if context is not None and isinstance(context, dict):
                 context.update({
                    "cmd": cmd,
                    "returncode": returncode,
                    "output_lines": output_lines,
                    "output": output
                })
            
            return False

        except Exception as e:
            if spinner:
                spinner.stop("ERROR", color="red", width=50)
            print(f"{colors.RED}Exception: {e}{colors.RESET}")
            return False

    if spinner:
        spinner.stop("FAILED", color="red", width=50)
    return False

def run_sync_command_with_retry(command, max_retries=3, interval=1):
    for attempt in range(max_retries):
        success = run_command_sync(command)

        if success:
            return True

        if attempt < max_retries - 1:
            time.sleep(interval)

    sys.exit(1)
    return False

def os_run(cmd, text=None, env=None):
    return run_command(cmd, message=text, env=env)

def os_run_output(cmd, env=None):
    return run_command_output(cmd, env=env)