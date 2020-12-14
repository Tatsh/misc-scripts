#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from typing import Iterator, Sequence, cast
import argparse
import plistlib
import re
import subprocess as sp
import sys

from typing_extensions import Final

try:
    import argcomplete
except ImportError:
    argcomplete = None

__all__ = ('main', )

KEY_WHEREFROMS: Final[str] = 'com.apple.metadata:kMDItemWhereFroms'


def hexstr2bytes(s: str) -> bytes:
    def chunks(l: str, n: int) -> Iterator[str]:
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def hexstr2bytes_generator(s: str) -> Iterator[int]:
        for hex_num in chunks(s, 2):
            yield int(hex_num, 16)

    return bytes(hexstr2bytes_generator(s))


def xattr(key: str, filename: str) -> str:
    return re.sub(
        r'\s+', '',
        sp.run(('xattr', '-p', key, filename),
               encoding='utf-8',
               stdout=sp.PIPE,
               check=True).stdout)


class Namespace(argparse.Namespace):
    files: Sequence[str]
    webpage: bool


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Determine where downloaded files came from.')
    parser.add_argument('files',
                        metavar='FILE',
                        nargs='+',
                        help='Files to process.')
    parser.add_argument('-w',
                        '--webpage',
                        action='store_true',
                        help='Print the webpage URL')
    if argcomplete:
        argcomplete.autocomplete(parser)
    args = cast(Namespace, parser.parse_args())
    has_multiple = len(args.files) > 1
    index = 1 if args.webpage else 0
    ret = 0
    for arg in args.files:
        try:
            val = cast(
                Sequence[str],
                plistlib.loads(hexstr2bytes(xattr(KEY_WHEREFROMS,
                                                  arg))))[index]
            if has_multiple:
                sys.stdout.write(f'{arg}: ')
            sys.stdout.write(f'{val}\n')
        except Exception:  # pylint: disable=broad-except
            ret = 1
        except KeyboardInterrupt:
            return 1
    return ret


if __name__ == '__main__':
    sys.exit(main())
