from collections.abc import Iterator, Sequence
from functools import cache
from pathlib import Path
import os
import re

from .itertools import chunks
from .system import IS_WINDOWS
from .typing import StrPath

__all__ = ('hexstr2bytes', 'hexstr2bytes_generator', 'is_ascii', 'strip_ansi',
           'strip_ansi_if_no_colors', 'underscorize', 'unix_path_to_wine')

ORD_MAX = 128
STRIP_ANSI_PATTERN = re.compile(r'\x1B\[\d+(;\d+){0,2}m')


@cache
def strip_ansi(o: str) -> str:
    """
    Remove ANSI escape sequences from `o`.
     
    As defined by ECMA-048 in http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-048.
    
    Taken from https://github.com/ewen-lbh/python-strip-ansi/ due to installation issues with
    Poetry.
    """
    return STRIP_ANSI_PATTERN.sub('', o)


def strip_ansi_if_no_colors(s: str) -> str:
    """See https://no-color.org/."""
    return strip_ansi(s) if os.environ.get('NO_COLOR') else s


def underscorize(s: str) -> str:
    return re.sub(r'\s+', '_', s)


def is_ascii(s: Sequence[str]) -> bool:
    """Check if a string consists of only ASCII characters."""
    return len(s) == len(''.join(y for y in s if ord(y) < ORD_MAX))


def hexstr2bytes_generator(s: str) -> Iterator[int]:
    for hex_num in chunks(s, 2):
        yield int(hex_num, 16)


def hexstr2bytes(s: str) -> bytes:
    return bytes(hexstr2bytes_generator(s))


def unix_path_to_wine(path: StrPath) -> str:
    if IS_WINDOWS:
        return str(path)
    try:
        path = Path(path).resolve(strict=True)
    except FileNotFoundError:
        path = Path.cwd() / path
    return f'Z:{path}'.replace('/', '\\')
