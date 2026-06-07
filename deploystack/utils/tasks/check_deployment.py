import subprocess
import os
import logging
import time
from dataclasses import dataclass, field

from ..core.system_utils import service_exists
from ..core import colors

MARKER_FILE = "/var/lib/openstack_installer/deploy_complete"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
#logger = logging.get#logger(__name__)

cinder_pkgs = ["cinder-api", "cinder-scheduler", "cinder-volume", "tgt"]

@dataclass
class CheckResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0

    def __str__(self):
        lines = [f"{colors.GREEN}PASSED:{colors.RESET} {s}" for s in self.passed] + [f"{colors.RED}FAILED:{colors.RESET} {s}" for s in self.failed]
        return "\n".join(lines)

def is_package_installed(pkg_name: str) -> bool:
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", pkg_name],
            capture_output=True, text=True, check=True
        )
        return "install ok installed" in result.stdout
    except subprocess.CalledProcessError:
        return False
    
def check_endpoint(service_name: str) -> bool:

    try:
        result = subprocess.run(
            ["openstack", "endpoint", "list", "--service", service_name,
             "-f", "value", "-c", "ID"],
            capture_output=True, text=True, timeout=10
        )
        return bool(result.stdout.strip())
    except FileNotFoundError:

        return False
    except subprocess.TimeoutExpired:

        return False


def check_service_active(svc: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", svc],
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:

        return False


def check_deployment(include_endpoints: bool = True):
    result = CheckResult()

    services_list = ["apache2", "glance-api"]

    if service_exists("nova-api.service"):
        services_list.append("nova-api")

    if service_exists("neutron-server.service"):
        services_list.append("neutron-server")
    elif service_exists("neutron-api.service"):
        services_list.append("neutron-api")
    else:
        services_list.append("neutron-periodic-workers")

    checks = [
        ("Services", services_list, check_service_active),
        ("Packages", ["apache2", "nova-common", "glance-api", "neutron-server"], is_package_installed),
        ("Config files", [
            "/etc/keystone/keystone.conf", "/etc/glance/glance-api.conf",
            "/etc/nova/nova.conf", "/etc/neutron/neutron.conf"
        ], os.path.isfile),
    ]

    def add_check(category, items, fn):
        checks.append((category, items, fn))

    if all(is_package_installed(pkg) for pkg in cinder_pkgs):
        add_check("Services", ["cinder-scheduler", "cinder-volume", "tgt"], check_service_active)
        add_check("Packages", cinder_pkgs, is_package_installed)
        add_check("Config files", ["/etc/cinder/cinder.conf", "/etc/tgt/conf.d/cinder.conf"], os.path.isfile)


    if include_endpoints:
        checks.append(
            ("Endpoints", ["identity", "compute", "image", "network"], check_endpoint)
        )

        if all(is_package_installed(pkg) for pkg in cinder_pkgs):
            add_check("Endpoints", ["volumev3"], check_endpoint)


    for category, items, check_fn in checks:
        for item in items:
            label = f"[{category}] {item}"
            if check_fn(item):
                result.passed.append(label)
            else:
                result.failed.append(label)

    return result

def check_env_variables():
    required_vars = [
        "OS_PROJECT_DOMAIN_NAME",
        "OS_USER_DOMAIN_NAME",
        "OS_PROJECT_NAME",
        "OS_USERNAME",
        "OS_PASSWORD",
        "OS_AUTH_URL",
        "OS_IDENTITY_API_VERSION",
        "OS_IMAGE_API_VERSION"
    ]

    missing = []
    empty = []

    for var in required_vars:
        value = os.environ.get(var)
        if value is None:
            missing.append(var)
        elif value.strip() == "":
            empty.append(var)

    if missing or empty:
        error_msg = []

        if missing:
            error_msg.append(f"Missing vars: {', '.join(missing)}")
        if empty:
            error_msg.append(f"Empty vars: {', '.join(empty)}")

        raise RuntimeError(" | ".join(error_msg))

if __name__ == "__main__":

    outcome = check_deployment(include_endpoints=False)
    print(outcome)

    if not outcome.ok:
        exit(1)

    try:
        check_env_variables()
    except RuntimeError as e:
        logging.error(f"Errore variabili d'ambiente: {e}")
        exit(1)

    endpoint_result = check_deployment(include_endpoints=True)
    print(endpoint_result)

    exit(0 if endpoint_result.ok else 1)

def check_cinder_installed() -> bool:

    if not all(is_package_installed(pkg) for pkg in cinder_pkgs): return False

    if not check_endpoint("volumev3"): return False

    if not all(check_service_active(service) for service in ["cinder-scheduler", "cinder-volume", "tgt"]) : return False
   
    return True

def is_cinder_installed() -> bool:

    if not check_cinder_installed():
        print(f"{colors.RED}Cinder service is not installed or not available.{colors.RESET}\n")
        print(f"{colors.YELLOW}  • If you want block storage support, run 'deploystack deploy --allinone' or include Cinder in your deployment{colors.RESET}")
        print(f"{colors.YELLOW}  • Alternatively, continue without Cinder, but volume-based features will not be available{colors.RESET}\n")
        return False

    return True   

def is_openstack_ready() -> bool:
    
    base_check = check_deployment(include_endpoints=False)
    if not base_check.ok or not os.path.exists(MARKER_FILE):
        print(f"{colors.RED}OpenStack is not deployed yet.{colors.RESET}\n")
        print(f"{colors.YELLOW}  • Run 'deploy --allinone' for a full automated deployment{colors.RESET}")
        print(f"{colors.YELLOW}  • Or run 'deploy --config-file <config_file>' with a custom config{colors.RESET}\n")
        return False

    try:
        check_env_variables()
    except RuntimeError:
        print(f"{colors.YELLOW}Shell is not authenticated. Source the environment file first:{colors.RESET}\n")
        print(f"  {colors.YELLOW}source /root/admin-openrc.sh{colors.RESET}  or")
        print(f"  {colors.GREEN}source /root/demo-openrc.sh{colors.RESET}\n")
        return False

    endpoint_check = check_deployment(include_endpoints=True)
    if not endpoint_check.ok:
        print(f"{colors.RED}OpenStack is deployed but services are not fully operational:{colors.RESET}")
        print(endpoint_check)
        return False

    return True

def mark_deployment_complete():
    os.makedirs(os.path.dirname(MARKER_FILE), exist_ok=True)
    with open(MARKER_FILE, "w") as f:
        f.write(f"Deployment completed at {time.ctime()}\n")