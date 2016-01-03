import os
import sys
from setuptools import find_packages, setup
from asgiref import __version__


# We use the README as the long_description
readme_path = os.path.join(os.path.dirname(__file__), "README.rst")


setup(
    name='asgiref',
    version=__version__,
    url='http://github.com/andrewgodwin/asgiref/',
    author='Andrew Godwin',
    author_email='andrew@aeracode.org',
    description='Reference ASGI adapters and channel layers',
    long_description=open(readme_path).read(),
    license='BSD',
    zip_safe=False,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'six',
    ]
)
