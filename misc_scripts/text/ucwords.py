#!/usr/bin/env python
import sys

from ..utils import ucwords

__all__ = ('main', )


def main() -> int:
    print('\n'.join(ucwords(x) for x in sys.stdin.readlines()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
