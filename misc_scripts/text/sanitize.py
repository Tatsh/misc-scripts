#!/usr/bin/env python
import sys

from ..utils import sanitize

__all__ = ('main', )


def main(s: str) -> int:
    print(sanitize(s))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
