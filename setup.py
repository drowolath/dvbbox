#!/usr/bin/env python
# encoding: utf-8

import os
from setuptools import setup, find_packages

datafiles = [
    ('/etc/dvbbox/', [os.path.join(d, f) for f in files])
    for d, folders, files in os.walk(os.path.abspath('example'))
    ]


def readme():
    with open('README.rst') as f:
        return f.read()
    
setup(
    name="dvbbox",
    version="3.2",
    packages=find_packages(),
    author="Thomas Ayih-Akakpo",
    author_email="thomas.ayih-akakpo@gulfsat.mg",
    description="Media files manager",
    long_description=readme(),
    license='Apache 2.0',
    include_package_data=True,
    data_files=datafiles,
    entry_points={
        'console_scripts': ['dvbbox=dvbbox:manager.run'],
        },
)
