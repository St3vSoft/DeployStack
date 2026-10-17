def get_base_host(config):
    network = config.get("network") or {}

    domain = network.get("HOST_DOMAIN")
    ip = network.get("HOST_IP")

    domain = domain.strip() if isinstance(domain, str) else None
    ip = ip.strip() if isinstance(ip, str) else None

    return domain or ip or None