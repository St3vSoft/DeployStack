import json
import time
import pwd
import grp
import subprocess
import os

from .....utils.core.spinner import Spinner

from .....utils.core.commands import os_run_output
from .....utils.core import colors

def user_in_group(username, groupname):
    try:
        user = pwd.getpwnam(username)
        group = grp.getgrnam(groupname)

        return (
            user.pw_gid == group.gr_gid or
            username in group.gr_mem
        )
    except KeyError:
        return False

def user_exists(username):
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

def samba_user_exists(username):
    try:
        result = subprocess.run(
            ["pdbedit", "-L"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False

    return any(line.partition(":")[0] == username for line in result.stdout.splitlines())

def create_manila_sudoers_rule():
    sudoers_content = "manila ALL=(root) NOPASSWD: /usr/bin/privsep-helper\n"

    with open("/etc/sudoers.d/manila-privsep", "w") as f:
        f.write(sudoers_content)

    os.chmod("/etc/sudoers.d/manila-privsep", 0o440)

def wait_manila_backend(env, timeout=120, interval=5):

    spinner = Spinner(message="Waiting for Share Service to become UP ...")
    spinner.start()

    deadline = time.time() + timeout
    last_check = 0

    try:
        while time.time() < deadline:
            now = time.time()

            if now - last_check >= interval:
                last_check = now

                try:
                    services = json.loads(
                        os_run_output(
                            ["openstack", "share", "service", "list", "-f", "json"],
                            env=env
                        ) or "[]"
                    )

                    for service in services:
                        if (
                            service.get("Binary", "").lower() == "manila-share"
                            and service.get("Status", "").lower() == "enabled"
                            and service.get("State", "").lower() == "up"
                        ):
                            spinner.stop(done_message="DONE", color="yellow", width=50)

                            return service

                except Exception:
                    pass

            time.sleep(0.1)

        spinner.stop(done_message="TIMEOUT", color="red", width=50)

        print(f"\n{colors.RED}ERROR: Manila share service did not become UP within {timeout}s {colors.RESET}\n")

        print(f"{colors.YELLOW}See manila-share logs for details.{colors.RESET}")

        return None

    finally:
        if spinner.running:
            spinner.stop(done_message="FAILED", color="red", width=50)

def wait_share_available(share_name, env, timeout=120, interval=5):

    spinner = Spinner(message=f"Waiting for share '{share_name}' to become available...")
    spinner.start()

    deadline = time.time() + timeout
    last_check = 0
    status = ""

    try:
        while time.time() < deadline:
            now = time.time()

            if now - last_check >= interval:
                last_check = now

                try:
                    share_info = json.loads(
                        os_run_output(
                            ["openstack", "share", "show", share_name, "-f", "json"],
                            env=env
                        ) or "{}"
                    )

                    status = share_info.get("status", "").lower()

                    if status == "available":
                        spinner.stop(done_message="DONE", color="yellow", width=60)
                        return share_info

                    if status in ("error", "error_deleting"):
                        spinner.stop(done_message="ERROR", color="red", width=60)

                        print(f"\n{colors.RED}ERROR: share '{share_name}' entered error state:{colors.RESET}\n")
                        
                        print(f"{colors.YELLOW}See manila-share logs for details.{colors.RESET}")

                        return None

                except Exception:
                    pass

            time.sleep(0.1)

        spinner.stop(done_message="TIMEOUT", color="red", width=60)

        print(
            f"\n{colors.RED}ERROR: {share_name} did not become available "
            f"within {timeout}s (last status: {status}){colors.RESET}"
        )

        return None

    finally:
        if spinner.running:
            spinner.stop(done_message="FAILED", color="red", width=60)

def wait_dhss_share_available(share_name, env, timeout=600, interval=10):

    spinner = Spinner(message=f"Waiting for share '{share_name}' to become available...")
    spinner.start()

    deadline = time.time() + timeout
    last_check = 0
    status = ""

    try:
        while time.time() < deadline:
            now = time.time()

            if now - last_check >= interval:
                last_check = now

                try:
                    share_info = json.loads(os_run_output(["openstack", "share", "show", share_name, "-f", "json"], env=env) or "{}")
                    status = share_info.get("status", "").lower()

                    if status == "available":
                        spinner.stop(done_message="DONE", color="yellow", width=60)
                        return share_info

                    if status in ("error", "error_deleting"):
                        spinner.stop(done_message="ERROR", color="red", width=60)

                        print(f"\n{colors.RED}ERROR: share '{share_name}' entered error state:{colors.RESET}\n")

                        print(f"{colors.YELLOW}See manila-share logs for details.{colors.RESET}")

                        return None

                except Exception:
                    pass

            time.sleep(0.1)

        spinner.stop(done_message="TIMEOUT", color="red", width=60)

        print(
            f"\n{colors.RED}ERROR: {share_name} did not become available "
            f"within {timeout}s (last status: {status}){colors.RESET}"
        )

        return None

    finally:
        if spinner.running:
            spinner.stop(done_message="FAILED", color="red", width=60)