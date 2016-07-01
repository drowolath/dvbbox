#!/usr/bin/env python
#encoding: utf-8


from setuptools import setup, find_packages

def readme():
    with open('README.rst') as f:
        return f.read()
    
setup(
    name="dvbbox",
    version="0.4",
    packages=['dvbbox'],
    author="Thomas Ayih-Akakpo",
    author_email="thomas@ayih-akakpo.org",
    description=("Library for managing static media files "
                 "and orchestrating their streaming"),
    long_description=readme(),
    license='MIT',
    include_package_data=True,
    entry_points = {
        'console_scripts': ['dvbbox=dvbbox:cli.run'],
        },
    url='http://github.com/drowolath/dvbbox.git',
)
