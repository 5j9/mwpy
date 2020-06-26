from os.path import abspath, dirname, join
from re import search, MULTILINE

from setuptools import setup


with open('README.rst', 'r') as fh:
    long_description = fh.read()

here = abspath(dirname(__file__))
setup(
    name='mwpy',
    version=search(
        r"^__version__ = '([^']*)'",
        open(
            join(here, 'mwpy', '__init__.py'),
            encoding='ascii', errors='ignore').read(),
        MULTILINE,
    ).group(1),
    author='5j9',
    author_email='5j9@users.noreply.github.com',
    description="An async MediaWiki client using trio and asks.",
    license='GNU General Public License v3 (GPLv3)',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/5j9/mwpy',
    packages=['mwpy'],
    python_requires='>=3.5',
    install_requires=['trio', 'asks'],
    tests_require=['pytest'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Environment :: Web Environment',
        'Framework :: Trio',
    ],
    zip_safe=True,
)
