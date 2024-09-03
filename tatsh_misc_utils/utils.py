from collections.abc import Iterator
from functools import lru_cache
import os
import platform
import re

__all__ = ('hexstr2bytes', 'strip_ansi', 'strip_ansi_if_no_colors')

IS_LINUX = platform.uname().system == 'Linux'
STRIP_ANSI_PATTERN = re.compile(r'\x1B\[\d+(;\d+){0,2}m')


@lru_cache
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


def hexstr2bytes(s: str) -> bytes:
    def chunks(seq: str, n: int) -> Iterator[str]:
        for i in range(0, len(seq), n):
            yield seq[i:i + n]

    def hexstr2bytes_generator(s: str) -> Iterator[int]:
        for hex_num in chunks(s, 2):
            yield int(hex_num, 16)

    return bytes(hexstr2bytes_generator(s))
