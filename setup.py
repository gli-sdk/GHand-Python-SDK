import os
import re

from setuptools import setup


def fetch_version():
    dir_path = os.path.abspath(os.path.dirname(__file__))
    version_file = os.path.join(dir_path, 'src', 'ghand', 'version.py')
    with open(version_file, encoding='utf-8') as f:
        content = f.read()
    match = re.search(r"__version__ = \"([^\"]+)\"", content)
    if not match:
        raise RuntimeError("Unable to find version string.")
    return match.group(1)


setup(version=fetch_version())
