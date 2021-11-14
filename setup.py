#!/usr/bin/env python3

# standards
from pathlib import Path
import re

# 3rd parties
import setuptools


version_file = Path(__file__).parent / 'hublot' / 'version.py'
version_match = re.search(
    r"HUBLOT_VERSION = \'(.+)\'",
    version_file.read_text('UTF-8'),
)
if not version_match:
    raise Exception("Couldn't parse version.py")
HUBLOT_VERSION = version_match.group(1)


setuptools.setup(
    name='hublot',
    version=HUBLOT_VERSION,
    author='Hervé Saint-Amand',
    packages=setuptools.find_packages(),
    package_data={'hublot': ['py.typed']},
    install_requires=[
        'dataclasses>=0.8,<1; python_version<"3.7"',
        'requests>=2.25,<3',
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
    zip_safe=False, # https://mypy.readthedocs.io/en/latest/installed_packages.html#creating-pep-561-compatible-packages
)
