#!/usr/bin/env python

import re
from setuptools import setup, find_packages

def get_version():
    """Fetch the project version number from the 'bmaptool' file."""

    with open("bmaptool", "r") as fobj:
        for line in fobj:
            matchobj = re.match(r'^VERSION = "(\d+.\d+)"$', line)
            if matchobj:
                return matchobj.group(1)

    return None

setup(
    name="bmap-tools",
    description="Bmap tools",
    author="Artem Bityutskiy",
    author_email="artem.bityutskiy@linux.intel.com",
    version=get_version(),
    scripts=['bmaptool'],
    packages=find_packages(exclude=["test*"]),
    license='GPLv2',
    long_description="Tools to generate block map (AKA bmap) and copy " \
                     "images using bmap",
)
