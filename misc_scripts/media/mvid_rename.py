#!/usr/bin/env python
from os.path import basename, isdir, realpath
from shutil import rmtree
import sys

__all__ = ('main', )


def _rename_and_trash(dir_: str) -> None:
    try:
        with open(f'{dir_}/{basename(dir_).lower()}.mkv', 'rb') as _in:
            with open(realpath(f'{dir_}/../{basename(dir_)}.mkv'),
                      'wb+') as out:
                out.write(_in.read())
            rmtree(dir_)
    except IOError:
        pass


def main() -> int:
    for x in (realpath(x) for x in sys.argv[1:]):
        if not isdir(x):
            continue
        _rename_and_trash(x)
    return 0


if __name__ == '__main__':
    sys.exit(main())
