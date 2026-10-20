import requests
import sys

from bs4 import BeautifulSoup

from .urls import CLOUD_IMAGE_URLS, debian_version_urls, centos_version_urls, centos_version_map, fedora_version_urls

from ....utils.core import colors

ARCH_MAP = {
    "amd64":  {"centos": "x86_64", "fedora": "x86_64"},
    "arm64":  {"centos": "aarch64", "fedora": "aarch64"},
}

def _get_latest_centos_url(version: str, arch: str) -> str:

    internal_ver = centos_version_map.get(version, version)
   
    if version in ("6", "7"):
        base_url = centos_version_urls[version]
    else:
        base_url = centos_version_urls["7+"].format(internal_ver=internal_ver, arch=arch)

    try:
        r = requests.get(base_url)
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f"Unable to fetch CentOS images with exception:\n {colors.RED}{e}{colors.RESET}")
        sys.exit(1)

    soup = BeautifulSoup(r.text, "html.parser")
    links = [a["href"] for a in soup.find_all("a") if a["href"].endswith(".qcow2")]

    if not links:
        print(f"{colors.RED}No CentOS QCOW2 images found for this version/arch{colors.RESET}")
        sys.exit(1)

    latest = sorted(links)[-1]
    return base_url + latest


def get_image_url(os:str, version: str, arch: str) -> str:

    os_name = os.lower()
    mapped_arch = ARCH_MAP.get(arch, {}).get(os_name, arch)

    if os_name == "centos":
        return _get_latest_centos_url(version, mapped_arch)
    
    elif os_name == "ubuntu":

        template = CLOUD_IMAGE_URLS[os_name]
        url = template.format(version=version, arch=arch)

        try:
            r = requests.head(url)
            if r.status_code >= 400:
                print(f"{colors.RED}Image not found at {url}{colors.RESET}")
                sys.exit(1)
        except requests.RequestException as e:
            print(f"{colors.RED}Failed to check Ubuntu image URL: {e}{colors.RESET}")
            sys.exit(1)

        return url
    
    elif os_name == "debian":

        url_template = debian_version_urls.get(version)
        if not url_template:
            print(f"{colors.RED}Unsupported Debian version: {version}{colors.RESET}")
            sys.exit(1)
       
        return url_template.format(arch=arch)
    
    elif os_name == "fedora":

        if version not in fedora_version_urls:
            print(f"{colors.RED}No Fedora image found for version {version}{colors.RESET}")
            sys.exit(1)
    
        url_template = fedora_version_urls[version]
        return url_template.format(arch=mapped_arch)

    if os_name in CLOUD_IMAGE_URLS:
        template = CLOUD_IMAGE_URLS[os_name]
        url = template.format(version=version, arch=mapped_arch)
      
        try:
            r = requests.head(url)
            if r.status_code >= 400:
                print(f"{colors.RED}Image not found at {url}{colors.RESET}")
                sys.exit(1)
        except requests.RequestException as e:
            print(f"{colors.RED}Failed to check image on URL: {e}{colors.RESET}")
            sys.exit(1)

        return url

    print(
    f"{colors.RED}[ERROR]{colors.RESET} No matching image found for:\n"
    f"  OS          : {colors.YELLOW}{os_name}{colors.RESET}\n"
    f"  Version     : {colors.YELLOW}{version}{colors.RESET}\n"
    f"  Architecture: {colors.YELLOW}{arch}{colors.RESET}\n"
    )

    print(f"Please verify your OS, version, or architecture and try again.")
    sys.exit(1)
