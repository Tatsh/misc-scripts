#!/usr/bin/env python
import sys

__all__ = ('main', )


def main() -> int:
    print('\n'.join(x.strip() for x in (
        sys.argv[1:] if len(sys.argv) >= 2 else sys.stdin.readlines())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
