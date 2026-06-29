
def norm(x):
    return (x or "").strip().lower()

def rule_matches(r, protocol, port, cidr):

    if (r.get("IP Protocol") or "").lower() != protocol.lower():
        return False

    if r.get("Direction") != "ingress":
        return False

    if protocol != "icmp":

        port_range = r.get("Port Range") or ""

        if ":" in port_range:
            a, b = port_range.split(":")
            if a != str(port) or b != str(port):
                return False
        else:
            if port_range != str(port):
                return False

    ip_range = r.get("IP Range") or ""

    if ip_range != cidr:
        return False

    return True