from setuptools import setup
import os

dir_path = os.path.abspath(os.path.dirname(__file__))


def fetch_version():
    with open(os.path.join(dir_path, 'src', 'ghand', 'version.py')) as f:
        ns = {}
        exec(f.read(), ns)
        return ns


ver = fetch_version()['__version__']

# Read all configuration from setup.cfg
setup(version=ver)
