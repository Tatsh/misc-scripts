from collections.abc import Sequence
from pathlib import Path
from time import sleep
from typing import Any, TextIO, TypeVar, cast, override
from urllib.parse import unquote_plus, urlparse
import json
import logging
import subprocess as sp
import sys

import click
import yaml

from .adp import calculate_salary
from .gentoo import (
    DEFAULT_ACTIVE_KERNEL_NAME,
    DEFAULT_KERNEL_LOCATION,
    DEFAULT_MODULES_PATH,
    clean_old_kernels_and_modules,
)
from .io import unpack_0day
from .string import is_ascii, sanitize, underscorize, unix_path_to_wine
from .system import IS_WINDOWS, inhibit_notifications, wait_for_disc
from .typing import DecodeErrorsOption, INCITS38Code
from .ultraiso import (
    InsufficientArguments,
    run_ultraiso,
)
from .utils import TIMES_RE, add_cdda_times
from .www import generate_html_dir_tree, where_from

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


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('path', type=click.Path(exists=True, dir_okay=True, file_okay=False), default='.')
@click.option('-d', '--depth', default=2, help='Maximum depth.', metavar='DEPTH')
@click.option('-f', '--follow-symlinks', is_flag=True, help='Follow symbolic links.')
@click.option('-o', '--output-file', type=click.File('w'), default=sys.stdout, help='Output file.')
def generate_html_dir_tree_main(path: str,
                                *,
                                output_file: TextIO,
                                depth: int = 2,
                                follow_symlinks: bool = False) -> None:
    """Generate a HTML directory listing."""
    click.echo(generate_html_dir_tree(path, follow_symlinks=follow_symlinks, depth=depth),
               output_file)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--appid', metavar='STRING', help='Application ID')
@click.option('--preparer', metavar='STRING', help='Preparer')
@click.option('--publisher', metavar='STRING', help='Publisher')
@click.option('--sysid', metavar='STRING', help='System ID')
@click.option('--volset', metavar='STRING', help='Volume Set ID', type=int)
@click.option('--volume', metavar='STRING', help='Volume label')
@click.option('--bootfile',
              metavar='FILENAME',
              help='Set boot file',
              type=click.Path(exists=True, dir_okay=False))
@click.option('--bootinfotable', is_flag=True, help='Generate boot information table in boot file')
@click.option('--optimize',
              is_flag=True,
              help='Optimise file systems by coding same files only once')
@click.option(
    '-f',
    '--file',
    'files',
    metavar='FILENAME',
    help='Add one file or folder (include folder name and all files and folders under it)',
    multiple=True,
    type=click.Path(exists=True))
@click.option(
    '--dir',
    'dirs',
    metavar='DIRNAME',
    multiple=True,
    help='Add all files and folders under given directory (not include directory name itself)',
    type=click.Path(exists=True))
@click.option('--newdir', metavar='DIRNAME', help='Create a new directory')
@click.option('-c', '--chdir', metavar='DIRNAME', help='Change current directory in ISO image')
@click.option('-r',
              '--rmdir',
              metavar='FILENAME',
              help='Remove a file or folder from ISO image (full path should be specified)')
@click.option('--hide',
              metavar='FILENAME',
              help='Set hidden attribute of a file or folder (full path should be specified)')
@click.option(
    '--ahide',
    metavar='FILENAME',
    help='Set advanced hidden attribute of a file or folder (full path should be specified)')
@click.option('-i',
              '--input',
              'input_',
              metavar='FILENAME',
              help='Input ISO image',
              type=click.Path(exists=True, dir_okay=False))
@click.option('-o', '--output', metavar='FILENAME', help='Output ISO image')
@click.option('--bin2iso',
              metavar='FILENAME',
              help='Convert input CD/DVD image to ISO format',
              type=click.Path(exists=True, dir_okay=False))
@click.option('--dmg2iso',
              metavar='FILENAME',
              help='Convert input DMG image to ISO format',
              type=click.Path(exists=True, dir_okay=False))
@click.option('--bin2isz',
              metavar='FILENAME',
              help='Compress input CD/DVD image to ISZ format',
              type=click.Path(exists=True, dir_okay=False))
@click.option('--compress', help='Set compression level', type=click.IntRange(1, 16))
@click.option('--encrypt', help='Set encryption method', type=click.IntRange(1, 3))
@click.option('--password',
              metavar='PASSWORD',
              help='Set ISZ password',
              prompt_required=True,
              hide_input=True)
@click.option('--split', metavar='SIZE', help='Set segment size in bytes', type=int)
@click.option('--list',
              'list_',
              metavar='FILENAME',
              help='Create a list of files and folders in an ISO image',
              type=click.Path(dir_okay=False))
@click.option('--get',
              metavar='FILENAME',
              help='Set a file or folder(full path should be specified) to be extracted')
@click.option('--extract', metavar='DIRNAME', help='Extract ISO image to specified directory')
@click.option('--cmd',
              metavar='FILENAME',
              help='Read arguments from a text file',
              type=click.Path(exists=True, dir_okay=False))
@click.option('-l',
              '--ilong',
              is_flag=True,
              help='Long filename for ISO 9660 volume, up to 31 chars')
@click.option('--imax', is_flag=True, help='Max filename for ISO 9660 volume, up to 207 chars')
@click.option('--vernum', is_flag=True, help='Include file version number')
@click.option('--lowercase', is_flag=True, help='Allow lowercase letter')
@click.option('--joliet', is_flag=True, help='Create Joliet volume')
@click.option('--jlong', is_flag=True, help='Long filename for joliet volume, up to 103 chars')
@click.option('--rockridge', is_flag=True, help='Create RockRidge volume')
@click.option('--udf', is_flag=True, help='Create UDF volume')
@click.option('--hfs', is_flag=True, help='Create Apple HFS volume')
@click.option('--udfdvd',
              is_flag=True,
              help='Create UDF DVD image (this option will overwrite all other volume settings)')
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
def ultraiso_main(ahide: str | None = None,
                  appid: str | None = None,
                  bin2iso: str | None = None,
                  bin2isz: str | None = None,
                  bootfile: str | None = None,
                  chdir: str | None = None,
                  cmd: str | None = None,
                  compress: int | None = None,
                  dirs: Sequence[str] | None = None,
                  dmg2iso: str | None = None,
                  encrypt: int | None = None,
                  extract: str | None = None,
                  files: Sequence[str] | None = None,
                  get: str | None = None,
                  hide: str | None = None,
                  input_: str | None = None,
                  list_: str | None = None,
                  newdir: str | None = None,
                  output: str | None = None,
                  password: str | None = None,
                  pn: int | None = None,
                  prefix: str | None = None,
                  preparer: str | None = None,
                  publisher: str | None = None,
                  rmdir: str | None = None,
                  split: int | None = None,
                  sysid: str | None = None,
                  volset: int | None = None,
                  volume: str | None = None,
                  *,
                  bootinfotable: bool = False,
                  hfs: bool = False,
                  ilong: bool = False,
                  imax: bool = False,
                  jlong: bool = False,
                  joliet: bool = False,
                  lowercase: bool = False,
                  optimize: bool = False,
                  rockridge: bool = False,
                  udf: bool = False,
                  udfdvd: bool = False,
                  vernum: bool = False,
                  debug: bool = False) -> None:
    """
    CLI interface to UltraISO.
    
    On non-Windows, runs UltraISO via Wine.
    """
    kwargs = {'prefix': prefix} if prefix and not IS_WINDOWS else {}
    logging.basicConfig(level=logging.ERROR if not debug else logging.DEBUG)
    try:
        run_ultraiso(add_dirs=dirs or [],
                     add_files=files or [],
                     bin2iso=bin2iso,
                     dmg2iso=dmg2iso,
                     bootfile=bootfile,
                     bootinfotable=bootinfotable,
                     optimize=optimize,
                     cmd=cmd,
                     chdir=chdir,
                     newdir=newdir,
                     rmdir=rmdir,
                     hfs=hfs,
                     jlong=jlong,
                     joliet=joliet,
                     rockridge=rockridge,
                     udf=udf,
                     udfdvd=udfdvd,
                     ahide=ahide,
                     hide=hide,
                     pn=cast(Any, pn),
                     appid=appid,
                     preparer=preparer,
                     publisher=publisher,
                     sysid=sysid,
                     volset=volset,
                     volume=volume,
                     input=input_,
                     bin2isz=bin2isz,
                     compress=cast(Any, compress),
                     encrypt=cast(Any, encrypt),
                     password=password,
                     split=split,
                     output=output,
                     extract=extract,
                     get=get,
                     list_=list_,
                     ilong=ilong,
                     imax=imax,
                     lowercase=lowercase,
                     vernum=vernum,
                     **kwargs)
    except (InsufficientArguments, sp.CalledProcessError) as e:
        raise click.Abort from e


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
@click.option('-t',
              '--sleep-time',
              default=0,
              type=int,
              help='Sleep time in seconds to inhibit notifications for.')
def inhibit_notifications_main(sleep_time: int = 60, *, debug: bool = False) -> None:
    """
    Disable notifications state for a time.

    On exit, notifications will be enabled. This command does nothing if notifications are already
    disabled.

    This is an alternative to ``kde-inhibit``. Unlike ``kde-inhibit``, this tool may only sleep.
    A sleep time of ``0`` effectively does nothing.
    """
    logging.basicConfig(level=logging.ERROR if not debug else logging.DEBUG)
    if inhibit_notifications():
        sleep(sleep_time)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
@click.option('-d', '--default-flow-style', is_flag=True, help='Enable compact flow style.')
@click.option('-i', '--indent', default=2, type=click.IntRange(2, 9), help='Indent width (spaces).')
def json2yaml_main(file: TextIO, indent: int = 2, *, default_flow_style: bool = False) -> None:
    """Convert JSON to YAML."""
    click.echo(yaml.dump(json.load(file), indent=indent, default_flow_style=default_flow_style))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
@click.option('-R', '--no-restricted', is_flag=True, help='Do not use restricted character set.')
def sanitize_main(file: TextIO, *, no_restricted: bool = False) -> None:
    """
    Transform a string to a 'sanitised' form.
    
    By default, a restricted character set safe for Windows filesnames is used. Disable with -R.
    """
    click.echo(sanitize(file.read(), restricted=not no_restricted))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filepath')
def unix2wine_main(filepath: str) -> None:
    """Convert a UNIX path to an absolute Wine path."""
    click.echo(unix_path_to_wine(filepath))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
def trim_main(file: TextIO) -> None:
    """Trim lines in file."""
    for line in file:
        click.echo(line.strip())


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
def ucwords_main(file: TextIO) -> None:
    """
    Run Python ``str.title()`` for lines in file.
    
    Named after PHP's function.
    """
    for line in file:
        click.echo(line.title(), nl=False)
