import ipaddress

def norm(x):
    return (x or "").strip().lower()

def rule_matches(r, protocol, port, cidr):
    if (r.get("IP Protocol") or "").lower() != protocol.lower():
        return False
    if (r.get("Direction") or "").lower() != "ingress":
        return False
    if (r.get("Ethertype") or "IPv4") != "IPv4":
        return False

    if protocol.lower() != "icmp":
        pr = (r.get("Port Range") or "").strip()
        if not pr:
            return False
        parts = pr.split(":")
        try:
            lo, hi = int(parts[0]), int(parts[-1])
        except ValueError:
            return False
        if not (lo <= int(port) <= hi):
            return False

    ip_range = (r.get("IP Range") or "").strip()
    try:
        return ipaddress.ip_network(ip_range, strict=False) == ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False