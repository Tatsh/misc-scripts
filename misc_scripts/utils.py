from functools import lru_cache
from os.path import basename, dirname, join as path_join, splitext
from typing import AnyStr, Callable, Optional, Sequence, TextIO, Union
from urllib.parse import urlparse
import json
import logging
import os
import re
import sys

__all__ = (
    'is_ascii',
    'is_roman_numeral',
    'isfile',
    'json2yaml',
    'netloc',
    'sanitize',
    'setup_logging',
    'setup_logging_stderr',
    'setup_logging_stdout',
    'slug_filename',
    'slug_rename',
    'slugify',
    'ucwords',
    'underscorize',
)


def is_ascii(lines: Sequence[str]) -> bool:
    return len(''.join(x.strip() for x in lines)) == len(''.join(
        (''.join(y for y in x.strip() if ord(y) < 128)) for x in lines))


def json2yaml(json_str: str) -> str:
    import yaml  # pylint: disable=import-outside-toplevel
    return yaml.dump(json.loads(json_str.strip()),
                     default_flow_style=False,
                     indent=2)


def sanitize(s: str) -> str:
    from youtube_dl.utils import sanitize_filename  # pylint: disable=import-outside-toplevel
    return re.sub(r'[_\-]+', '-',
                  sanitize_filename(s, restricted=True).lower())


def slugify(s: str) -> str:
    return re.sub(r'[-\s_]+', '-', re.sub(r'[^\w\s-]', '', s).strip().lower())


def slug_filename(arg: str) -> str:
    name, ext = splitext(arg)
    if ext in ('.bz2', '.gpg', '.gz'):
        name, ext2 = splitext(name)
        ext = f'{ext2}{ext}'
    name = re.sub(r'[-\s_]+', '-', re.sub(r'[^\w\s-]', '',
                                          basename(name))).strip().lower()
    return path_join(dirname(arg), name) + ext.lower()


def slug_rename(arg: str) -> None:
    return os.replace(arg, slug_filename(arg))


def is_roman_numeral(string: str) -> bool:
    if not string.strip():
        return False
    # https://l.tat.sh/2HXEIyx
    return re.match(
        r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$', string,
        re.I) is not None


def ucwords(val: str) -> str:
    return val.strip().title()


def netloc(val: str) -> str:
    return urlparse(val).netloc.strip()


def underscorize(s: Sequence[str]) -> str:
    return re.sub(r'\s+', '_', ' '.join(s))


def setup_logging(out: TextIO) -> Callable[..., logging.Logger]:
    @lru_cache()
    def func(name: Optional[str] = None,
             verbose: Optional[bool] = False) -> logging.Logger:
        name = name if name else basename(sys.argv[0])
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG if verbose else logging.INFO)
        channel = logging.StreamHandler(out)
        channel.setFormatter(logging.Formatter('%(message)s'))
        channel.setLevel(logging.DEBUG if verbose else logging.INFO)
        log.addHandler(channel)
        return log

    return func


setup_logging_stderr = setup_logging(sys.stderr)
setup_logging_stdout = setup_logging(sys.stdout)


def isfile(f: Union[AnyStr, int]) -> bool:
    try:
        with open(f, 'rb'):
            return True
    except IOError:
        pass
    return False
