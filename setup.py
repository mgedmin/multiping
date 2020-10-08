#!/usr/bin/env python3
import ast
import os
import re

from setuptools import setup


here = os.path.dirname(__file__)
with open(os.path.join(here, "README.rst")) as f:
    long_description = f.read()

metadata = {}
with open(os.path.join(here, "multiping.py")) as f:
    rx = re.compile("(__version__|__author__|__url__|__licence__) = (.*)")
    for line in f:
        m = rx.match(line)
        if m:
            metadata[m.group(1)] = ast.literal_eval(m.group(2))
version = metadata["__version__"]

setup(
    name="multiping.py",
    version=version,
    author="Marius Gedminas",
    author_email="marius@gedmin.as",
    url="https://github.com/mgedmin/multiping",
    project_urls={
        'Changelog':
            'https://github.com/mgedmin/multiping/blob/master/CHANGES.rst',
    },
    description="ncurses frontend to ping",
    long_description=long_description,
    long_description_content_type='text/x-rst',
    keywords="ping ncurses",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: Console :: Curses",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    license="GPL",
    python_requires=">=3.6",

    py_modules=["multiping"],
    zip_safe=False,
    install_requires=[],
    extras_require={
        'test': [
            'mock',
        ],
    },
    entry_points={
        "console_scripts": [
            "multiping = multiping:main",
        ],
    },
)
