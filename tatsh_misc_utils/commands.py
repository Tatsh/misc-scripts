from collections.abc import Sequence
from pathlib import Path
from typing import TextIO, TypeVar, override
from urllib.parse import unquote_plus, urlparse
import sys

import click

from .adp import calculate_salary
from .gentoo import (
    DEFAULT_ACTIVE_KERNEL_NAME,
    DEFAULT_KERNEL_LOCATION,
    DEFAULT_MODULES_PATH,
    clean_old_kernels_and_modules,
)
from .string import is_ascii, underscorize
from .typing import DecodeErrorsOption, INCITS38Code
from .utils import TIMES_RE, add_cdda_times, unpack_0day, wait_for_disc, where_from

CONTEXT_SETTINGS = {'help_option_names': ('-h', '--help')}


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('drive_path', type=click.Path(exists=True, dir_okay=False, writable=True))
@click.option('-w',
              '--wait-time',
              type=float,
              default=1.0,
              help='Wait time in seconds.',
              metavar='TIME')
def wait_for_disc_main(drive_path: str, wait_time: float = 1.0) -> None:
    """Wait for a disc in a drive to be ready."""
    if not wait_for_disc(drive_path, sleep_time=wait_time):
        raise click.Abort


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-H', '--hours', default=160, help='Hours worked in a month.', metavar='HOURS')
@click.option('-r', '--pay-rate', default=70.0, help='Dollars per hour.', metavar='DOLLARS')
@click.option(
    '-s',
    '--state',
    metavar='STATE',
    default='FL',
    type=click.Choice(INCITS38Code.__args__),  # type: ignore[attr-defined]
    help='US state abbreviation.')
def adp_main(hours: int = 160, pay_rate: float = 70.0, state: INCITS38Code = 'FL') -> None:
    """Calculate US salary."""
    click.echo(str(calculate_salary(hours=hours, pay_rate=pay_rate, state=state)))


_T = TypeVar('_T', bound=str)


class CDDATimeStringParamType(click.ParamType):
    name = 'cdda_time_string'

    @override
    def convert(self, value: _T, param: click.Parameter | None, ctx: click.Context | None) -> _T:
        if TIMES_RE.match(value):
            return value
        self.fail(f'{value!r} is not a valid CDDA time string.', param, ctx)
        return None  # type: ignore[unreachable]


@click.command(context_settings=CONTEXT_SETTINGS,
               epilog='Example invocation: add-cdda-times 01:02:73 02:05:09')
@click.argument('times', nargs=-1, type=CDDATimeStringParamType())
def add_cdda_times_main(times: tuple[str, ...]) -> None:
    """Add CDDA timestamps together.
    
    A CDDA timestamp is 3 zero-prefixed integers MM:SS:FF, separated by colons. FF is the number of
    frames out of 75.
    """
    if (result := add_cdda_times(times)) is None:
        raise click.Abort
    click.echo(result)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('files',
                metavar='FILE',
                nargs=-1,
                type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('-w', '--webpage', is_flag=True, help='Print the webpage URL (macOS only).')
def where_from_main(files: Sequence[str], *, webpage: bool = False) -> None:
    """Display URL where a file was downloaded from."""
    has_multiple = len(files) > 1
    for arg in files:
        if has_multiple:
            click.echo(f'{arg}: ', nl=False)
        click.echo(where_from(arg, webpage=webpage))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
def is_ascii_main(file: TextIO) -> None:
    if not is_ascii(file.read()):
        raise click.exceptions.Exit(1)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-e', '--encoding', default='utf-8', help='Text encoding.')
@click.option(
    '-r',
    '--errors',
    default='strict',
    type=click.Choice(DecodeErrorsOption.__args__),  # type: ignore[attr-defined]
    help='Error handling mode.')
@click.argument('file', type=click.File('r'), default=sys.stdin)
def urldecode_main(file: TextIO,
                   encoding: str = 'utf-8',
                   errors: DecodeErrorsOption = 'strict') -> None:
    is_netloc = Path(sys.argv[0]).stem == 'netloc'
    for line in file:
        val = unquote_plus(line, encoding, errors)
        if is_netloc:
            val = urlparse(val).netloc.strip()
        click.echo(val.strip())


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
def underscorize_main(file: TextIO) -> None:
    for line in file:
        click.echo(underscorize(line.strip()))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('dirs',
                nargs=-1,
                metavar='DIR',
                type=click.Path(exists=True, dir_okay=True, file_okay=False))
def unpack_0day_main(dirs: Sequence[str]) -> None:
    """Unpack RAR files from 0day zip file sets."""
    for path in dirs:
        unpack_0day(path)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('path',
                type=click.Path(exists=True, dir_okay=True, file_okay=False),
                default=DEFAULT_KERNEL_LOCATION)
@click.option('--active-kernel-name',
              help='Kernel name like "linux".',
              default=DEFAULT_ACTIVE_KERNEL_NAME)
@click.option('-m',
              '--modules-path',
              type=click.Path(exists=True, dir_okay=True, file_okay=False),
              help='Location where modules get installed, such as "/lib/modules".',
              default=DEFAULT_MODULES_PATH)
@click.option('-q', '--quiet', help='Prevent output.', is_flag=True)
def clean_old_kernels_and_modules_main(path: str = DEFAULT_KERNEL_LOCATION,
                                       modules_path: str = DEFAULT_MODULES_PATH,
                                       active_kernel_name: str = DEFAULT_ACTIVE_KERNEL_NAME,
                                       *,
                                       quiet: bool = False) -> None:
    """
    Remove inactive kernels and modules.
    
    By default, removes old Linux sources from /usr/src.
    """
    for item in clean_old_kernels_and_modules(path, modules_path, active_kernel_name):
        if not quiet:
            click.echo(item)
