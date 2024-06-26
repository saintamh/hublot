#!/usr/bin/env python3

# standards
from pathlib import Path
import re

# 3rd parties
import setuptools


def get_version() -> str:
    version_file = Path(__file__).parent / "hublot" / "version.py"
    version_match = re.search(
        r"HUBLOT_VERSION = \"(.+)\"",
        version_file.read_text("UTF-8"),
    )
    if not version_match:
        raise ValueError("Couldn't parse version.py")
    return version_match.group(1)


setuptools.setup(
    name="hublot",
    version=get_version(),
    description="A thin wrapper around Requests that adds caching and throttling",
    url="https://github.com/saintamh/hublot",
    author="Hervé Saint-Amand",
    packages=setuptools.find_packages(exclude=["test"]),
    package_data={"hublot": ["py.typed"]},
    install_requires=[
        "chardet>= 3.0.2,<5",  # version req copied from requests
        'dataclasses>=0.8,<1; python_version<"3.7"',
        "requests>=2.25,<3",
    ],
    extras_require={
        "pycurl": [
            "pycurl>=7,<8",
        ],
    },
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ],
    zip_safe=False,  # https://mypy.readthedocs.io/en/latest/installed_packages.html#creating-pep-561-compatible-packages
)
