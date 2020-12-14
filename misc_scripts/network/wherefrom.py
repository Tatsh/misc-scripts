#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from typing import Sequence, cast
import argparse
import plistlib
import sys

from typing_extensions import Final

from ..utils import hexstr2bytes, xattr

try:
    import argcomplete
except ImportError:
    argcomplete = None

__all__ = ('main', )

KEY_WHEREFROMS: Final[str] = 'com.apple.metadata:kMDItemWhereFroms'


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
