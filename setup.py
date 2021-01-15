#!/usr/bin/env python3

# they're both standards, pylint: disable=wrong-import-order
import setuptools
import sys


install_requires = []
if sys.version_info < (3, 7):
    install_requires.append('dataclasses>=0.8,<1')


setuptools.setup(
    name='forban',
    version='1.0',
    author='Hervé Saint-Amand',
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
)
