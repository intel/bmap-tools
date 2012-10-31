#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name = "bmap-tools",
    description = "Bmap tools",
    author = "Artem Bityutskiy",
    author_email = "artem.bityutskiy@linux.intel.com",
    version = "0.1.0",
    scripts = ['bmap-flasher', 'bmap-creator'],
    packages = find_packages(),
    license='GPLv2',
    long_description="Tools to generate block map (AKA bmap) and flash " \
                     "images using bmap",
)
