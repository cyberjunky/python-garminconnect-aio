#!/usr/bin/env python

from setuptools import setup

with open("README.md") as readme_file:
    readme = readme_file.read()

setup(
    author="Ron Klinkien",
    author_email="ron@cyberjunky.nl",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    description="Asynchronous Garmin Connect Python 3 API wrapper",
    name="garminconnect_aio",
    keywords=["garmin connect", "api", "client"],
    license="MIT license",
    install_requires=["aiohttp >= 3.6", "yarl", "brotlipy"],
    long_description_content_type="text/markdown",
    long_description=readme,
    url="https://github.com/cyberjunky/python-garminconnect-aio",
    packages=["garminconnect_aio"],
    version="0.1.2",
)
