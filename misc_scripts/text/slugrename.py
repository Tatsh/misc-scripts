#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
import argparse
import sys

from ..utils import slug_filename, slug_rename

try:
    import argcomplete
except ImportError:
    argcomplete = None

__all__ = ('main', )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('-y', '--dry-run', action='store_true')
    parser.add_argument('files', nargs='*')
    if argcomplete:
        argcomplete.autocomplete(parser)
    args = parser.parse_args()
    arg: str
    for arg in args.files:
        if args.dry_run:
            print(slug_filename(arg))
        else:
            slug_rename(arg)
    return 0


if __name__ == '__main__':
    sys.exit(main())
