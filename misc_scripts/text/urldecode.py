#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from typing import Iterable, Iterator, Literal, cast
from urllib.parse import unquote_plus
import argparse
import sys

from ..utils import netloc

try:
    import argcomplete
except ImportError:
    argcomplete = None

__all__ = ('main', )


def parse(
    values: Iterable[str],
    is_netloc: bool = False,
    encoding: str = 'utf-8',
    errors: Literal['strict', 'replace',
                    'ignore'] = 'replace') -> Iterator[str]:
    for x in values:
        val = unquote_plus(x, encoding=encoding, errors=errors)
        yield netloc(val) if is_netloc else val


class Namespace(argparse.Namespace):
    encoding: str
    errors: Literal['strict', 'replace', 'ignore']
    string: str


def main() -> int:
    is_netloc = sys.argv[0].endswith('netloc')
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--encoding', default='utf-8')
    parser.add_argument('-r', '--errors', default='replace')
    is_atty = sys.stdin.isatty()
    if is_atty:
        parser.add_argument('string', nargs='*')
    if argcomplete:
        argcomplete.autocomplete(parser)
    args = cast(Namespace, parser.parse_args())
    print('\n'.join(
        parse(args.string if is_atty else sys.stdin.readlines(),
              is_netloc=is_netloc,
              encoding=args.encoding,
              errors=args.errors)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
