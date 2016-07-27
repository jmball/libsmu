#!/usr/bin/env python

from io import open
import glob
import os
import re
import subprocess
import sys

from distutils.command.build_ext import build_ext as dst_build_ext
from distutils.command.sdist import sdist as dst_sdist
from setuptools import setup, find_packages, Extension, Command
from Cython.Build import cythonize

# top level bindings directory
BINDINGS_DIR = os.path.dirname(os.path.abspath(__file__))
# top level repo directory
TOPDIR = os.path.dirname(os.path.dirname(BINDINGS_DIR))


class RunCommand(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


class PyTest(RunCommand):
    user_options = [('match=', 'k', 'Run only tests that match the provided expressions')]

    def initialize_options(self):
        self.match = None

    def run(self):
        cli_options = ['-k', self.match] if self.match else []
        os.environ['EPYTHON'] = 'python{}.{}'.format(sys.version_info.major, sys.version_info.minor)
        errno = subprocess.call(['py.test'] + cli_options)
        raise SystemExit(errno)


def pkgconfig(*packages, **kw):
    """Translate pkg-config data to compatible Extension parameters."""
    flag_map = {'-I': 'include_dirs', '-L': 'library_dirs', '-l': 'libraries'}

    try:
        tokens = subprocess.check_output(
            ['pkg-config', '--libs', '--cflags'] + list(packages)).split()
    except OSError as e:
        sys.stderr.write('running pkg-config failed: {}\n'.format(e.strerror))
        sys.exit(1)

    for token in tokens:
        token = token.decode()
        if token[:2] in flag_map:
            kw.setdefault(flag_map.get(token[:2]), []).append(token[2:])
        else:
            kw.setdefault('extra_compile_args', []).append(token)
    return kw


# configure various required compile flags
ext_kwargs = {'include_dirs': [os.path.join(TOPDIR, 'include')]}
if sys.platform == 'win32':
    ext_kwargs['libraries'] = ['libsmu']
else:
    ext_kwargs['libraries'] = ['smu']
    ext_kwargs = pkgconfig('libusb-1.0', **ext_kwargs)

# cython/cpp extensions to generate/build
extensions = []
extensions.extend([
    Extension(
        'pysmu.libsmu',
        [os.path.join(BINDINGS_DIR, 'pysmu', 'libsmu.pyx')], **ext_kwargs),
    ])


class sdist(dst_sdist):
    """Make sure generated cython files are included."""

    def run(self):
        cythonize(extensions)
        dst_sdist.run(self)


class build_ext(dst_build_ext):
    """Add custom compile flags for compiled extensions."""

    def build_extensions(self):
        compiler = self.compiler.compiler_type
        cxxflags = []
        if compiler != 'msvc':
            cxxflags.append('-std=c++11')
        for ext in self.extensions:
            ext.extra_compile_args.extend(cxxflags)
        return dst_build_ext.build_extensions(self)


version = ''
with open('pysmu/__init__.py', 'r') as fd:
    reg = re.compile(r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]')
    for line in fd:
        m = reg.match(line)
        if m:
            version = m.group(1)
            break

if not version:
    raise RuntimeError('Cannot find version information')

setup(
    name='pysmu',
    version=version,
    description='python library for the ADALM1000 device',
    url='https://github.com/analogdevicesinc/libsmu',
    license='BSD',
    author='Tim Harder',
    author_email='radhermit@gmail.com',
    packages=find_packages(),
    ext_modules=cythonize(extensions),
    scripts=glob.glob('bin/*'),
    tests_require=['pytest'],
    cmdclass={
        'build_ext': build_ext,
        'sdist': sdist,
        'test': PyTest,
    },
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)
