#!/usr/bin/env python3

# they're all standards, pylint: disable=wrong-import-order
import setuptools
import sys

# forban
from forban.version import FORBAN_VERSION


install_requires = [
    'requests>=2.25,<3',
]
if sys.version_info < (3, 7):
    install_requires.append('dataclasses>=0.8,<1')


setuptools.setup(
    name='forban',
    version=FORBAN_VERSION,
    author='Hervé Saint-Amand',
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
)
