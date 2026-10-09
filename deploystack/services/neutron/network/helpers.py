
def norm(x):
    return (x or "").strip().lower()

def rule_matches(r, protocol, port, cidr):
    
    if (r.get("IP Protocol") or "").lower() != protocol.lower():
        return False

    if (r.get("Direction") or "").lower() != "ingress":
        return False

    if protocol.lower() != "icmp":
        port_range = (r.get("Port Range") or "").strip()

        if not port_range:
            return False

        ports = port_range.split(":")

        if len(ports) == 1:
            if ports[0] != str(port):
                return False
        elif len(ports) == 2:
            if not (int(ports[0]) <= int(port) <= int(ports[1])):
                return False
        else:
            return False

    ip_range = (r.get("IP Range") or "").strip()

    if ip_range != cidr:
        return False

    return True