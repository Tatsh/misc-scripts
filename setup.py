"""Module for package-specific tasks."""
from os import listdir
from typing import Iterator
import pathlib

from setuptools import setup

EXCEPTIONS = {
    'misc_scripts.chrome:bookmarks2csv': 'chrome-bookmarks2csv',
    'misc_scripts.chrome:link': 'chrome-link',
}


def find_scripts() -> Iterator[str]:
    p = pathlib.Path(__file__).parent.absolute().joinpath('misc_scripts')
    for item in listdir(p):
        full = p.joinpath(item)
        if not full.is_dir():
            continue
        for module in listdir(full):
            if (module in ('__init__.py', 'utils.py')
                    or not module.endswith('.py')):
                continue
            module = module.replace('.py', '')
            command = module.replace('_', '-')
            path = f'misc_scripts.{item}:{module}'
            if path in EXCEPTIONS:
                yield f'{EXCEPTIONS[path]} = {path}'
            else:
                yield f'{command} = {path}'


setup(
    author='Andrew Udvare',
    author_email='audvare@gmail.com',
    classifiers=['Topic :: Utilities'],
    description='Random scripts.',
    license='LICENSE.txt',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    name='misc-scripts',
    python_requires='>=3.8',
    url='https://github.com/Tatsh/misc-scripts',
    version='0.0.1',
    install_requires=(
        'BeautifulSoup4',
        'PyYAML',
        'argcomplete',  # only required for auto-complete behaviour
        'binaryornot',
        'lxml',
        'python-magic',
        'requests',
        'typing-extensions',
        'youtube-dl',  # only required for sanitize
    ),
    entry_points={
        'console_scripts':
        list(find_scripts()) + [
            f'flac-{x} = misc_scripts.media:flacted'
            for x in ('album', 'artist', 'genre', 'title', 'track', 'year')
        ] + ['netloc = misc_scripts.text:urldecode']
    })
