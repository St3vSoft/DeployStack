import json

from ..network.helpers import rule_matches
from ....utils.core import colors
from ....utils.core.commands import os_run, os_run_output

def add_rules_to_default_sg(
    create_bridges: bool,
    rules_dict,
    ip_prefix,
    sg_id: str,
    rules,
    env,
) -> bool:

    for name, rule in rules_dict.items():
        if not rule.get("enabled"):
            continue

        port = rule.get("port")
        protocol = rule.get("protocol", "tcp").lower()
        rule_type = name.upper()

        rule_exists = any(rule_matches(r, protocol, port, ip_prefix) for r in rules)

        if rule_exists:
            print(f"{colors.YELLOW}{rule_type} rule in security group '{sg_id}' already exists, skipping creation.{colors.RESET}")
            continue

        if not create_bridges:
            continue

        cmd = [
            "openstack", "security", "group", "rule", "create",
            "--proto", protocol,
        ]

        if protocol != "icmp":
            cmd += ["--dst-port", str(port)]

        cmd += ["--remote-ip", ip_prefix, sg_id]

        if os_run(
            cmd,
            f"Allowing {rule_type} access in security group '{sg_id}'...",
            env=env,
        ):
            continue

        try:
            updated_rules = json.loads(os_run_output(["openstack", "security", "group", "rule", "list", sg_id, "-f", "json"], env=env))
        except Exception:
            return False

        if any(rule_matches(r, protocol, port, ip_prefix) for r in updated_rules):
            rules[:] = updated_rules
            continue

        return False

    return True