import os
import sys
from setuptools import find_packages, setup


# We use the README as the long_description
readme_path = os.path.join(os.path.dirname(__file__), "README.rst")


setup(
    name='asgi_inmemory',
    version="0.8",
    url='http://github.com/andrewgodwin/asgi_inmemory/',
    author='Andrew Godwin',
    author_email='andrew@aeracode.org',
    description='Reference in-memory ASGI channel layer implementation',
    long_description=open(readme_path).read(),
    license='BSD',
    zip_safe=False,
    packages=find_packages(),
    include_package_data=True,
)
