from setuptools import setup, find_packages
from pathlib import Path
import sys

info = {}

is_debian_like = (
    info.get("ID") == "debian"
    or "debian" in info.get("ID_LIKE", "").split()
)

if sys.platform.startswith("win") or sys.platform == "darwin":
    print("This package is not supported on Windows or macOS platforms.")
    sys.exit(1)

if not is_debian_like:
    print("This utility requires a Debian-based Linux distribution (e.g. Debian or Ubuntu).")
    sys.exit(1)

setup(
    name="DeployStack",
    version="1.0.0",
    description="DeployStack is a command-line utility for deploying OpenStack on Debian.",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/St3vSoft/DeployStack",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "psutil",
        "python-dotenv",
        "PyYAML",
        "requests",
        "tqdm",
        "bs4",
        "passlib"
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "deploystack=deploystack.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
)