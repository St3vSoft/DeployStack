import subprocess
import sys

from ..detach.runner import reset_volume_state
from ..detach.runner import is_uuid, get_volume_id_from_name
from ..remove.runner import check_volume_attached

from ....utils.core import colors

from ...shell import _run, is_uuid, logger

def is_volume_available(volume: str) -> bool:
       
    check_volume_status_cmd = [
        "openstack", "volume", "show", volume, "-f", "value", "-c", "status"
    ]

    try:
        result = subprocess.run(check_volume_status_cmd, capture_output=True, text=True, check=True)
        volume_status = result.stdout.strip()

        if volume_status == "available":
             return True
        elif volume_status == "in-use":
             return False
        else:
            logger.warning(f"{colors.YELLOW}Volume {volume} has unexpected status '{volume_status}'{colors.RESET}")
            return False
        
    except subprocess.CalledProcessError as e:
        logger.error(f"{colors.RED}Error while trying to listing volume info: {e}{colors.RESET}\n")
        sys.exit(1)


def reset(
    volume: str,
    force: bool
):
       volume_id = volume if is_uuid(volume) else get_volume_id_from_name(volume)

       if not force:
            if is_volume_available(volume_id):
                    print(f"{colors.YELLOW}The '{volume}' volume is already in an available state, no action needed!{colors.RESET}\n")
                    sys.exit(1)

            check_volume_attached(volume_id)
       
       print(f"Resetting volume '{volume_id}' status ...\n")
       reset_volume_state(volume_id)

       print(
            f"{colors.GREEN}Volume '{volume}' "
            f"(ID: {volume_id}) status successfully resetted!{colors.RESET}"
        )