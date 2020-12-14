#!/usr/bin/env python
import sys

__all__ = ('main', )


def main():
    for line in sys.stdin.readlines():
        print(line.strip().title())


if __name__ == '__main__':
    sys.exit(main())
