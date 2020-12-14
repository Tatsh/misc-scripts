#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from typing import Sequence, cast
import argparse
import sys

from ..utils import underscorize

try:
    import argcomplete
except ImportError:
    argcomplete = None

__all__ = ('main', )


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Replaces white space with underscores')
    parser.add_argument('strings',
                        metavar='STRING',
                        default=sys.stdin,
                        nargs='*',
                        help='Strings to process')
    if argcomplete:
        argcomplete.autocomplete(parser)
    print(underscorize(cast(Sequence[str], parser.parse_args().strings)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
