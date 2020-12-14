#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from copy import copy
from os.path import basename
from typing import Any, Iterable, Optional, Tuple, cast
import argparse
import subprocess as sp
import sys

from ..utils import setup_logging_stdout

try:
    import argcomplete
except ImportError:
    argcomplete = None

__all__ = ('main', )


def metaflac(*args: Any) -> str:
    return sp.run(('metaflac', ) + cast(Tuple[str, ...], args),
                  check=True,
                  stdout=sp.PIPE,
                  encoding='utf-8').stdout


class Namespace(argparse.Namespace):
    album: Optional[str]
    artist: Optional[str]
    delete_all_before: Optional[bool]
    files: Iterable[str]
    genre: Optional[str]
    picture: Optional[str]
    title: Optional[str]
    year: Optional[str]


def main() -> int:
    setup_logging_stdout()
    log = setup_logging_stdout()
    invoked_as = basename(sys.argv[0])
    if invoked_as != 'flacted' and len(sys.argv) >= 2:
        tag_requested = invoked_as.split('-')[1]
        possible: Tuple[str,
                        ...] = (tag_requested.title(), tag_requested.upper(),
                                tag_requested.lower())
        if tag_requested.lower() == 'year':
            possible += ('Date', 'DATE', 'date')
        unfiltered_files = sys.argv[1:]
        files = []
        for file in unfiltered_files:
            try:
                with open(file):
                    files.append(file)
            except FileNotFoundError:
                pass
        show_filename = len(files) > 1
        for filename in files:
            for tag in possible:
                val = metaflac(f'--show-tag={tag}', filename).strip()
                try:
                    val = val[len(tag) + 1:].splitlines()[0].strip()
                except IndexError:
                    val = ''
                if val:
                    if tag_requested.lower() == 'track':
                        try:
                            val_int: Optional[int] = int(val)
                        except TypeError:
                            val = ''
                            val_int = None
                        if val_int:
                            val = f'{val_int:02d}'
                    if show_filename:
                        log.info('%s: %s', filename, val)
                    else:
                        log.info('%s', val)
                    break
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--title')
    parser.add_argument('-a', '--artist')
    parser.add_argument('-A', '--album')
    parser.add_argument('-y', '--year')
    parser.add_argument('-T', '--track')
    parser.add_argument('-g', '--genre')
    parser.add_argument('-p', '--picture')
    parser.add_argument('-D', '--delete-all-before', action='store_true')
    parser.add_argument('files', metavar='FILES', nargs='+')
    if argcomplete:
        argcomplete.autocomplete(parser)
    args = cast(Namespace, parser.parse_args())
    metaflac_args = ['--preserve-modtime', '--no-utf8-convert']
    cleanup_args = copy(metaflac_args)
    destroy = args.delete_all_before
    cleanup_args.append('--remove-all-tags')
    cleanup_args.extend(args.files)
    for key in ('title', 'artist', 'album', 'year', 'track', 'genre'):
        val = getattr(args, key, None)
        if not val:
            continue
        val = val.strip()
        if key == 'year':
            flac_tag = 'Date'
        elif key == 'track':
            flac_tag = 'Tracknumber'
        else:
            flac_tag = f'{key[0].upper()}{key[1:]}'
        metaflac_args.append(f'--set-tag={flac_tag}={val}')
    if args.picture:
        try:
            with open(args.picture, 'rb'):
                metaflac_args.append(f'--import-picture-from={args.picture}')
        except IOError:
            log.error(
                'Cannot add file "%s". Specified argument is not '
                'supported', args.picture)
            return 1
    if len(metaflac_args) == 2:
        log.error('Not doing anything')
        return 1
    if destroy:
        metaflac(*cleanup_args)
    metaflac_args.extend(args.files)
    metaflac(*metaflac_args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
