"""Module for package-specific tasks."""
from os import listdir
from typing import Iterator, Tuple
import pathlib

from setuptools import setup


def find_scripts() -> Iterator[str]:
    mod_path = (
        pathlib.Path(__file__).parent.absolute().joinpath('misc_scripts'))

    def _find_them() -> Iterator[Tuple[str, str, str, str]]:
        for item, modules, prefix in ((x, listdir(y),
                                       'chrome-' if x == 'chrome' else '')
                                      for x, y in ((x, mod_path.joinpath(x))
                                                   for x in listdir(mod_path))
                                      if y.is_dir()):
            yield from ((item, m, prefix, n)
                        for m, n in ((n, n.replace('_', '-')) for n in (
                            m.replace('.py', '') for m in modules
                            if m.endswith('.py') and m not in ('__init__.py',
                                                               'utils.py'))))

    for item, module, prefix, command in _find_them():
        yield f'{prefix}{command} = misc_scripts.{item}:{module}'


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
