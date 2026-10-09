
import os

from pathlib import Path

from ....utils.core.commands import run_command

encap_modules = {
    "vxlan": ["vport_vxlan", "vxlan"],
    "geneve": ["vport_geneve", "geneve"],
}

ifaces_config_exclude_patterns = {
    "openvswitch",
    "br-shares",
}

def write_permanent_modules_conf(file_path: str, modules: list[str]):
    modules_file = Path(file_path)
    
    modules_file.parent.mkdir(parents=True, exist_ok=True)
    modules_file.write_text("\n".join(modules) + "\n")

def enable_ipv4_forwarding() -> bool:
    with open("/proc/sys/net/ipv4/ip_forward") as f:
        ip_forward = int(f.read().strip())

    if ip_forward != 1:

        if not run_command(
            ["sysctl", "-w", "net.ipv4.ip_forward=1"],
            "Enabling IPv4 IP Forwarding..."
        ):
            return False
        else:
            print()

    sysctl_file = "/etc/sysctl.d/99-openstack-forwarding.conf"

    if not os.path.exists(sysctl_file):
        with open(sysctl_file, "w") as f:
            f.write("net.ipv4.ip_forward = 1\n")

    return True
