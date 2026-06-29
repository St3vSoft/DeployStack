
from ..network.helpers import rule_matches
from ....utils.core import colors
from ....utils.core.commands import os_run

def add_rules_to_default_sg(create_bridges: bool, rules_dict, ip_prefix, sg_id: str, rules, env) -> bool:
    
    for name, rule in rules.items():

        if not rule.get("enabled"):
            continue

        port = rule.get("port")
        protocol = rule.get("protocol", "tcp")
        rule_type = name.upper()

        is_icmp = protocol == "icmp"

        rule_exists = any(
            rule_matches(r, protocol, port, ip_prefix)
            for r in rules_dict
        )

        if create_bridges and not rule_exists:

            cmd = [
                "openstack", "security", "group", "rule", "create",
                "--proto", protocol,
            ]

            if not is_icmp:
                cmd += ["--dst-port", str(port)]

            cmd += ["--remote-ip", ip_prefix, sg_id]

            if not os_run(cmd, f"Allowing {rule_type} access...", env=env):
                return False
        else:
            print(f"{colors.YELLOW}{rule_type} rule already exists, skipping creation{colors.RESET}")

    return True