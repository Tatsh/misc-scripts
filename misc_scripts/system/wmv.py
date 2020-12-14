#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from typing import List, Sequence, cast
import argparse
import subprocess as sp
import sys

from ..text.w2c import make_target
from ..utils import setup_logging_stdout

try:
    import argcomplete
except ImportError:
    argcomplete = None


class Namespace(argparse.Namespace):
    b: bool
    backup: bool
    file: Sequence[str]
    force: bool
    interactive: bool
    no_clobber: bool
    no_target_directory: bool
    strip_trailing_slashes: bool
    suffix: str
    target_directory: str
    update: bool
    verbose: bool


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Renames file names with full-width characters to normal '
        'width name. Please see `man mv` or `info coreutils \'mv invocation\'`'
        ' for option arguments')
    # ilm mv | grep -E '^‘\-' | cut -c 2- | sed -e "s/’$//"
    parser.add_argument('--backup')
    parser.add_argument('-b', action='store_true')
    parser.add_argument('-f', '--force', action='store_true')
    parser.add_argument('-i', '--interactive', action='store_true')
    parser.add_argument('-n', '--no-clobber', action='store_true')
    parser.add_argument('-u', '--update', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--strip-trailing-slashes', action='store_true')
    parser.add_argument('-S', '--suffix')
    parser.add_argument('-t', '--target-directory')
    parser.add_argument('-T', '--no-target-directory', action='store_true')
    parser.add_argument('file', metavar='SOURCE', nargs=1, help='Source')
    if argcomplete:
        argcomplete.autocomplete(parser)
    args = cast(Namespace, parser.parse_args())
    log = setup_logging_stdout(verbose=args.verbose)
    special_values = (
        ('--backup', args.backup),
        ('--suffix', args.suffix),
        ('--target-directory', args.target_directory),
    )
    bool_args = (
        ('--backup', args.b),
        ('--force', args.force),
        ('--interactive', args.interactive),
        ('--no-clobber', args.no_clobber),
        ('--update', args.update),
        ('--strip-trailing-slashes', args.strip_trailing_slashes),
    )
    mv_args: List[str] = []
    if args.b and args.backup:
        log.error('Cannot use -b and --backup simultaneously')
        return 1
    for arg, val in special_values:
        if isinstance(val, str):
            mv_args.append(f'{arg}={val}')
    for arg, val in bool_args:
        if val is True:
            mv_args.append(arg)
    command = ['mv'] + mv_args + [args.file[0], make_target(args.file[0])]
    log.info('Command: %s', ' '.join(command))
    try:
        p = sp.run(command,
                   stdout=sp.PIPE,
                   stderr=sp.PIPE,
                   encoding='utf-8',
                   check=True)
    except sp.CalledProcessError as e:
        log.error('STDOUT: %s', e.output)
        log.error('STDERR: %s', e.stderr)
        return e.returncode
    if '-v' in mv_args or '--verbose' in mv_args:
        log.info('%s', p.stdout)
    return 0


if __name__ == '__main__':
    sys.exit(main())
