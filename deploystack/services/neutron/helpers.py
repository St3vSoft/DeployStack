
def norm(x):
    return (x or "").strip().lower()

def rule_matches(r, protocol, port, cidr):
    if norm(r.get("IP Protocol")) != norm(protocol):
        return False

    if norm(r.get("Direction")) != "ingress":
        return False

    if norm(protocol) == "icmp":
        return True

    # TCP/UDP
    port_range = r.get("Port Range") or ""

    # gestisce "80" e "80:80"
    if ":" in port_range:
        start, end = port_range.split(":")
        if not (start == str(port) and end == str(port)):
            return False
    else:
        if port_range != str(port):
            return False

    if cidr and r.get("Remote IP Prefix") != cidr:
        return False

    return True