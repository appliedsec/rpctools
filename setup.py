"""
The rpctools package provides client libraries for working with RPC services
with enhanced SSL support.
"""
import re
import os.path
import warnings
try:
    from setuptools import setup, find_packages
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

version = '0.3.1'

long_description = """
The rpctools package provides client libraries for working with RPC services
with enhanced SSL support.

Currently the only protocol implemented is JSON-RPC.  The enhanced SSL
support is simply that these libraries can present client certificates
for authentication and can be set up to require a trusted SSL connection with
the server (validating CA and hostname matches).
"""

pkg_name = 'rpctools'

setup(
    name=pkg_name,
    version=version,
    description=__doc__,
    long_description=long_description,
    keywords='jsonrpc json-rpc rpc client ssl',
    license='Apache',
    packages=find_packages(exclude=['tests', 'ez_setup']),
    include_package_data=True,
    zip_safe=True,
    author='Hans Lellelid',
    author_email='hans@xmpl.org',
    url='http://github.com/appliedsec/rpctools',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
