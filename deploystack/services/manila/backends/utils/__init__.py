import json
import time

from .....utils.core.commands import os_run_output
from .....utils.core import colors

def wait_manila_backend(env, timeout=120):
    elapsed = 0

    while elapsed < timeout:
        services = json.loads(
            os_run_output(
                ["openstack", "share", "service", "list", "-f", "json"],
                env=env
            )
        )

        for service in services:
            if (
                service["Binary"] == "manila-share"
                and service["State"] == "up"
                and service["Status"] == "enabled"
            ):
                return True

        time.sleep(5)
        elapsed += 5

    return False

def wait_share_available(share_name, env, timeout=120, interval=5):
    print(f"\nWaiting for share '{share_name}' to become available ", end="", flush=True)

    deadline = time.time() + timeout
    spinner = "|/-\\"
    spinner_index = 0

    status = ""

    while time.time() < deadline:
        try:
            share_info = json.loads(
                os_run_output(
                    ["openstack", "share", "show", share_name, "-f", "json"],
                    env=env
                ) or "{}"
            )

            status = share_info.get("status", "").lower()

            if status == "available":
                print(f"\rWaiting for share '{share_name}' to become available [ {colors.YELLOW}DONE{colors.RESET} ]")
                return share_info

            if status in ("error", "error_deleting"):
                print(
                    f"\n{colors.RED}ERROR: {share_name} entered error state: {status}{colors.RESET}"
                )
                return None

        except Exception:
            pass

        print(f"\b{spinner[spinner_index]}", end="", flush=True)
        spinner_index = (spinner_index + 1) % len(spinner)

        time.sleep(interval)

    print(
        f"\n{colors.RED}ERROR: {share_name} did not become available "
        f"within {timeout}s (last status: {status}){colors.RESET}"
    )

    return None

def wait_dhss_share_available(share_name, env, timeout=600, interval=10):
    print(f"\nWaiting for share '{share_name}' to become available ", end="", flush=True)

    deadline = time.time() + timeout
    spinner = "|/-\\"
    spinner_index = 0

    while time.time() < deadline:
        try:
            share_info = json.loads(
                os_run_output(
                    ["openstack", "share", "show", share_name, "-f", "json"],
                    env=env
                ) or "{}"
            )

            status = share_info.get("status", "").lower()

            if status == "available":
                print(f"\b {colors.YELLOW}DONE{colors.RESET}")
                return share_info

            if status == "error":
                print(f"\n{colors.RED}Error: share '{share_name}' is in error state{colors.RESET}\n")
                return None

        except Exception:
            pass

        print(f"\b{spinner[spinner_index]}", end="", flush=True)
        spinner_index = (spinner_index + 1) % len(spinner)

        time.sleep(interval)

    print(f"\n{colors.RED}Error: timeout waiting for share '{share_name}'{colors.RESET}")
    return None