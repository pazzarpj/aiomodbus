#!/usr/bin/env python
from setuptools import setup, find_packages

import sys
import os
import re

BASE_LOCATION = os.path.abspath(os.path.dirname(__file__))

REQUIRES_FILE = 'requirements.txt'


def get_version():
    with open(os.path.join("aiomodbus", "__init__.py")) as f:
        return re.search("__version__ = [\"\']([\w.]+)", f.read()).group(1)


def filter_comments(fd):
    no_comments = list(filter(lambda l: l.strip().startswith("#") is False, fd.readlines()))
    lines = list(filter(lambda l: l.strip().startswith("-") is False, no_comments))
    lines = list(filter(lambda l: l.strip().startswith("git+") is False, lines))
    return [l.strip() for l in lines]


def readfile(filename, func):
    try:
        with open(os.path.join(BASE_LOCATION, filename)) as f:
            data = func(f)
    except (IOError, IndexError):
        sys.stderr.write(u"""
Can't find '%s' file. This doesn't seem to be a valid release.
""" % filename)
        sys.exit(1)
    return data


def get_requires():
    return readfile(REQUIRES_FILE, filter_comments)


setup(
    name="aiomodbus",
    author="Ryan Parry-Jones",
    author_email="ryanspj+github@gmail.com",
    description="Lightweight Modbus library using asyncio",
    packages=find_packages(''),
    scripts=[],
    version=get_version(),
    install_requires=get_requires(),
    python_requires='>=3.6',
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Intended Audience :: Manufacturing",
        "Intended Audience :: Telecommunications Industry"
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Development Status :: 2 - Pre-Alpha"
    ]
)
