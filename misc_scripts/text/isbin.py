#!/usr/bin/env python
import sys

from binaryornot.check import is_binary

from ..utils import isfile

__all__ = ('main', )


def main() -> int:
    if not isfile(sys.argv[1]):
        return 1
    return 0 if is_binary(sys.argv[1]) else 1


if __name__ == '__main__':
    sys.exit(main())
