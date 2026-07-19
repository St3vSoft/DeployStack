
import grp
import subprocess
import json

from ...utils.core.commands import run_command

def get_vg_for_pv(device):
    try:
        result = subprocess.run(
            ["pvs", "--reportformat", "json", "-o", "pv_name,vg_name"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None

    data = json.loads(result.stdout)

    for pv in data["report"][0]["pv"]:
        if pv["pv_name"] == device:
            return pv["vg_name"] or None

    return None

def ensure_system_user_with_run_command(username="cinder"):
    success = True

    try:
        grp.getgrnam(username)
    except KeyError:
        if not run_command(
            ["groupadd", username],
            message=f"Creating group {username}",
            ignore_errors=False
        ):
            success = False

    try:
        pwd.getpwnam(username)
    except KeyError:
        if not run_command(
            ["useradd", "-r", "-s", "/bin/false", username],
            message=f"Creating system user {username}",
            ignore_errors=False
        ):
            success = False

    return success