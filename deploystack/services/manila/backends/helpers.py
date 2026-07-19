import json
import time

from ....utils.core.commands import os_run_output
from ....utils.core import colors

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
    elapsed = 0

    while elapsed < timeout:
        share_info = json.loads(
            os_run_output(
                ["openstack", "share", "show", share_name, "-f", "json"],
                env=env
            )
        )

        status = share_info.get("status")

        if status == "available":
            return share_info

        if status in ("error", "error_deleting"):
            print(
                f"{colors.RED}ERROR: {share_name} entered error state: {status}{colors.RESET}"
            )
            return None

        time.sleep(interval)
        elapsed += interval

    print(
        f"{colors.RED}ERROR: {share_name} did not become available "
        f"within {timeout}s (last status: {status}){colors.RESET}"
    )

    return None