#!/usr/bin/env python
import sys
from ..utils import is_ascii

__all__ = ('main', )


def main() -> int:
    return (1 if not is_ascii(
        sys.argv[1:] if len(sys.argv) > 1 else sys.stdin.readlines()) else 0)


if __name__ == '__main__':
    sys.exit(main())
