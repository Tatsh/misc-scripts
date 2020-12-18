#!/usr/bin/env python
import sys

from ..utils import slugify

__all__ = ('main', )


def main() -> int:
    print(slugify(sys.argv[1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
