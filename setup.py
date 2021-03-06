#!/usr/bin/env python3

# standards
from pathlib import Path
import re

# 3rd parties
import setuptools


version_file = Path(__file__).parent / 'forban' / 'version.py'
version_match = re.search(
    r"FORBAN_VERSION = \'(.+)\'",
    version_file.read_text('UTF-8'),
)
if not version_match:
    raise Exception("Couldn't parse version.py")
FORBAN_VERSION = version_match.group(1)


setuptools.setup(
    name='forban',
    version=FORBAN_VERSION,
    author='Hervé Saint-Amand',
    packages=setuptools.find_packages(),
    install_requires=[
        'dataclasses>=0.8,<1; python_version<"3.7"',
        'requests>=2.25,<3',
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
)
