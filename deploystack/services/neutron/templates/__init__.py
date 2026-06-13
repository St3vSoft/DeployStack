import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _t(*parts) -> str:
    return os.path.join(BASE_DIR, *parts)

INTERFACE_BRIDGE_TEMPLATE         = _t("iface_br.tpl")