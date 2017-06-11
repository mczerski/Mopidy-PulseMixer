from __future__ import unicode_literals

import re

from setuptools import find_packages, setup


def get_version(filename):
    content = open(filename).read()
    metadata = dict(re.findall("__([a-z]+)__ = '([^']+)'", content))
    return metadata['version']


setup(
    name='Mopidy-PulseMixer',
    version=get_version('mopidy_pulsemixer/__init__.py'),
    url='https://github.com/mczerski/mopidy-pulsemixer',
    license='Apache License, Version 2.0',
    author='Marek Czerski',
    author_email='ma.czerski@gmail.com',
    description='Mopidy extension for Pulseaudio volume control',
    long_description=open('README.rst').read(),
    packages=find_packages(exclude=['tests', 'tests.*']),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        'setuptools',
        'Mopidy >= 2.0',
        'Pykka >= 1.1',
        'pulsectl',
    ],
    entry_points={
        'mopidy.ext': [
            'pulsemixer = mopidy_pulsemixer:Extension',
        ],
    },
    classifiers=[
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Topic :: Multimedia :: Sound/Audio :: Players',
    ],
)
