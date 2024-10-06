from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from shlex import quote, split
from shutil import which
from time import sleep
from typing import Any, TextIO, TypeVar, cast, override
from urllib.parse import unquote_plus, urlparse
import contextlib
import errno
import getpass
import json
import logging
import plistlib
import re
import socket
import subprocess as sp
import sys
import webbrowser

from binaryornot.check import is_binary
from git import Repo
from paramiko import SSHClient
from requests import HTTPError
from send2trash import send2trash
import click
import github
import keyring
import pyperclip
import requests
import xdg.BaseDirectory
import yaml

from .adp import calculate_salary
from .gentoo import (
    DEFAULT_ACTIVE_KERNEL_NAME,
    DEFAULT_KERNEL_LOCATION,
    DEFAULT_MODULES_PATH,
    clean_old_kernels_and_modules,
)
from .git import (
    convert_git_ssh_url_to_https,
    get_github_default_branch,
    merge_dependabot_pull_requests,
)
from .io import unpack_0day
from .media import (
    add_info_json_to_media_file,
    create_static_text_video,
    get_info_json,
    supported_audio_input_formats,
)
from .string import (
    fullwidth_to_ascii,
    is_ascii,
    is_url,
    sanitize,
    slugify,
    underscorize,
    unix_path_to_wine,
)
from .system import (
    IS_LINUX,
    IS_WINDOWS,
    find_bluetooth_device_info_by_name,
    inhibit_notifications,
    slug_rename,
    wait_for_disc,
)
from .typing import DecodeErrorsOption, INCITS38Code
from .ultraiso import (
    InsufficientArguments,
    run_ultraiso,
)
from .utils import (
    TIMES_RE,
    WineWindowsVersion,
    add_cdda_times,
    create_wine_prefix,
    secure_move_path,
)
from .www import generate_html_dir_tree, upload_to_imgbb, where_from

CONTEXT_SETTINGS = {'help_option_names': ('-h', '--help')}
_T = TypeVar('_T', bound=str)


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

    By default, a restricted character set safe for Windows filenames is used. Disable with -R.
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


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('rb'), default=sys.stdin)
def pl2json_main(file: BytesIO) -> None:
    """
    Convert a Property List file to JSON.

    This command does not do any type conversions. This means files containing <data> objects will
    not work.
    """
    try:
        click.echo(json.dumps(plistlib.load(file), sort_keys=True, allow_nan=False, indent=2))
    except TypeError as e:
        click.echo('A non-JSON serialisable item is present in the file.', err=True)
        raise click.Abort from e


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('origin_name', metavar='ORIGIN_NAME', default='origin')
@click.option('-b',
              '--base-url',
              default=github.Consts.DEFAULT_BASE_URL,
              help='Base URL for enterprise.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-u', '--username', default=getpass.getuser(), help='Username (passed to keyring).')
def git_checkout_default_branch_main(base_url: str,
                                     username: str,
                                     origin_name: str = 'origin',
                                     *,
                                     debug: bool = False) -> None:
    """
    Checkout to the default branch.

    For repositories whose origin is on GitHub only.

    To set a token, ``keyring set tmu-github-api "${USER}"``. The token must have
    access to the public_repo or repo scope.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    token = keyring.get_password('tmu-github-api', username)
    if not token:
        click.echo('No token.', err=True)
        raise click.Abort
    repo = Repo(search_parent_directories=True)
    default_branch = get_github_default_branch(repo=repo,
                                               base_url=base_url,
                                               token=token,
                                               origin_name=origin_name)
    next(b for b in repo.heads if b.name == default_branch).checkout()


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('origin_name', metavar='ORIGIN_NAME', default='origin')
@click.option('-b',
              '--base-url',
              default=github.Consts.DEFAULT_BASE_URL,
              help='Base URL for enterprise.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-u', '--username', default=getpass.getuser(), help='Username (passed to keyring).')
@click.option('-r',
              '--remote',
              is_flag=True,
              help='Rebase with the origin copy of the default branch.')
def git_rebase_default_branch_main(base_url: str,
                                   username: str,
                                   origin_name: str = 'origin',
                                   *,
                                   debug: bool = False,
                                   remote: bool = False) -> None:
    """
    Rebase the current head with the default branch.

    For repositories whose origin is on GitHub only.

    To set a token, ``keyring set tmu-github-api "${USER}"``. The token must have
    access to the public_repo or repo scope.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    token = keyring.get_password('tmu-github-api', username)
    if not token:
        click.echo('No token.', err=True)
        raise click.Abort
    repo = Repo(search_parent_directories=True)
    default_branch = get_github_default_branch(repo=repo,
                                               base_url=base_url,
                                               token=token,
                                               origin_name=origin_name)
    repo.git.rebase(f'{origin_name}/{default_branch}' if remote else default_branch)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('name', default='origin')
def git_open_main(name: str = 'origin') -> None:
    """Open assumed repository web representation (GitHub, GitLab, etc) based on the origin."""
    url = Repo(search_parent_directories=True).remote(name).url
    if re.search(r'^https?://', url):
        webbrowser.open(url)
        return
    webbrowser.open(convert_git_ssh_url_to_https(url))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
def is_bin_main(file: str) -> None:
    """
    Check if a file has binary contents.

    For this utility, 0 byte files do not count as binary.

    Exit code 0 means the file probably contains binary content.
    """
    if Path(file).stat().st_size != 0 and is_binary(file):
        return
    raise click.exceptions.Exit(1)


@click.command(context_settings={**CONTEXT_SETTINGS, 'auto_envvar_prefix': 'UMPV'})
@click.option('-d', '--debug', is_flag=True)
@click.option('--mpv-command', default='mpv', help='mpv command including arguments.')
@click.argument('files', nargs=-1)
def umpv_main(files: Sequence[str], mpv_command: str = 'mpv', *, debug: bool = False) -> int:
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    log = logging.getLogger(__name__)
    fixed_files = ((p if is_url(p) else str(Path(p).resolve(strict=True))) for p in files)
    socket_path = str(Path(xdg.BaseDirectory.xdg_state_home) / 'umpv-socket')
    sock = None
    socket_connected = False
    try:
        sock = socket.socket(socket.AF_UNIX)
        sock.connect(socket_path)
        socket_connected = True
    except OSError as e:
        if e.errno == errno.ECONNREFUSED:
            log.debug('Socket refused connection')
            sock = None  # abandoned socket
        elif e.errno == errno.ENOENT:
            log.debug('Socket does not exist')
            sock = None  # does not exist
        else:
            log.exception('Socket errno: %d', e.errno)
            raise
    if sock and socket_connected:
        # Unhandled race condition: what if mpv is terminating right now?
        for f in fixed_files:
            # escape: \ \n "
            g = f.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            log.debug('Loading file "%s"', f)
            sock.send(f'raw loadfile "{g}"\n'.encode())
    else:
        log.debug('Starting new mpv instance')
        # Let mpv recreate socket if it does not already exist
        args = (*split(mpv_command), *(() if debug else ('--no-terminal',)), '--force-window',
                f'--input-ipc-server={socket_path}', '--', *fixed_files)
        log.debug('Command: %s', ' '.join(quote(x) for x in args))
        sp.run(args, check=True)
    return 0


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--debug', is_flag=True)
@click.option('--device',
              'device_name',
              default='hci0',
              help='Bluetooth device (defaults to hci0).')
def connect_g603_main(device_name: str = 'hci0', *, debug: bool = False) -> None:
    """
    Connect a G603 Bluetooth mouse, disconnecting/removing first if necessary.

    For Linux only.

    This is useful for connecting the mouse back when it randomly decides not to re-pair, and you
    have no other mouse but you can get to your terminal.
    """
    if not IS_LINUX:
        click.echo('Only Linux is supported.', err=True)
        raise click.Abort
    from gi.overrides.GLib import GError, Variant  # noqa: PLC0415
    from gi.repository import GLib  # noqa: PLC0415
    from pydbus import SystemBus  # noqa: PLC0415
    loop = GLib.MainLoop()
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    log = logging.getLogger(__name__)
    bus = SystemBus()
    adapter = bus.get('org.bluez', f'/org/bluez/{device_name}')

    def on_properties_changed(_: Any, __: Any, object_path: str, ___: Any, ____: Any,
                              props: Variant) -> None:
        dev_iface = props[0]
        values = props[1]
        if dev_iface == 'org.bluez.Adapter1' and values.get('Discovering'):
            log.debug('Scan on.')
        elif (dev_iface == 'org.bluez.Device1'
              and (m := re.match(fr'/org/bluez/{device_name}/dev_(.*)', object_path))):
            mac = m.group(1).replace('_', ':')
            for k in ('ServicesResolved', 'Connected'):
                if k in values and not values[k]:
                    log.debug('Device %s was disconnected.', mac)
                    return
            try:
                device = bus.get('org.bluez', object_path)
                if device.Name != 'G603':
                    log.debug('Ignoring device %s (MAC: %s).', device.Name, mac)
                    return
            except (GError, KeyError) as e:
                log.debug('Caught error with device %s: %s', mac, str(e))
                return
            if values.get('Paired'):
                log.debug('Quitting.')
                loop.quit()
                return
            if 'RSSI' in values:
                click.echo(f'Pairing with {mac}.')
                device['org.bluez.Device1'].Pair()
            else:
                log.debug('Unhandled property changes: interface=%s, values=%s, mac=%s', dev_iface,
                          values, mac)

    # PropertiesChanged.connect()/.PropertiesChanged = ... will not catch the device node events
    bus.con.signal_subscribe(None, 'org.freedesktop.DBus.Properties', 'PropertiesChanged', None,
                             None, 0, on_properties_changed)
    log.debug('Looking for existing devices.')
    with contextlib.suppress(KeyError):
        while res := find_bluetooth_device_info_by_name('G603'):
            object_path, info = res
            log.debug('Removing device with MAC address %s.', info['Address'])
            adapter.RemoveDevice(object_path)
    click.echo('Put the mouse in pairing mode and be very patient.')
    log.debug('Starting scan.')
    adapter.StartDiscovery()
    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.argument('device')
def supported_audio_input_formats_main(device: str, *, debug: bool = False) -> None:
    """Get supported input formats and sample rates by invoking ffmpeg."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    try:
        for format_, rate in supported_audio_input_formats(device):
            click.echo(f'{format_} @ {rate}')
    except OSError as e:
        click.echo('Likely invalid device name.', err=True)
        raise click.Abort from e


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.argument('filename', type=click.Path(exists=True, dir_okay=False), nargs=-1)
def add_info_json_main(filename: tuple[str], *, debug: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    for f in filename:
        add_info_json_to_media_file(f, debug=debug)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.argument('filename', type=click.Path(exists=True, dir_okay=False))
def display_info_json_main(filename: str, *, debug: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    try:
        click.echo(get_info_json(filename, raw=True))
    except NotImplementedError as e:
        raise click.Abort from e
    except sp.CalledProcessError as e:
        click.echo(e.stdout)
        click.echo(e.stderr)
        raise click.Abort from e


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-f', '--font', default='Roboto', help='Font to use.')
@click.option('-n', '--nvenc', is_flag=True, help='Use NVENC.')
@click.option('-V', '--videotoolbox', is_flag=True, help='Use VideoToolbox.')
@click.argument('audio_filename', type=click.Path(exists=True, dir_okay=False))
@click.argument('text')
def audio2vid_main(audio_filename: str,
                   text: str,
                   font: str = 'Roboto',
                   *,
                   debug: bool = False,
                   nvenc: bool = False,
                   videotoolbox: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    create_static_text_video(audio_filename,
                             text,
                             font,
                             nvenc=nvenc,
                             videotoolbox=videotoolbox,
                             debug=debug)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
def fullwidth2ascii_main(file: TextIO) -> None:
    click.echo(fullwidth_to_ascii(file.read()), nl=False)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('r'), default=sys.stdin)
@click.option('--no-lower', is_flag=True, help='Disable lowercase.')
def slugify_main(file: TextIO, *, no_lower: bool = False) -> None:
    click.echo(slugify(file.read(), no_lower=no_lower))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filenames', nargs=-1)
@click.option('--no-lower', is_flag=True, help='Disable lowercase.')
@click.option('-v', '--verbose', is_flag=True, help='Enable verbose output.')
def slug_rename_main(filenames: tuple[str, ...],
                     *,
                     no_lower: bool = False,
                     verbose: bool = False) -> None:
    for name in filenames:
        target = slug_rename(name, no_lower=no_lower)
        if verbose:
            click.echo(f'{name} -> {target}')


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('prefix_name')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-r', '--prefix-root', type=click.Path(), help='Prefix root.')
@click.option('-S', '--sandbox', is_flag=True, help='Sandbox the prefix.')
@click.option(
    '-V',
    '--windows-version',
    default='xp',
    type=click.Choice(WineWindowsVersion.__args__),  # type: ignore[attr-defined]
    help='Windows version.')
@click.option('--vd',
              metavar='SIZE',
              nargs=1,
              default='off',
              help='Virtual desktop size, e.g. 1024x768.')
@click.option('--no-xdg', is_flag=True, help='Disable winemenubuilder.exe')
@click.option('--32', '_32bit', help='Use 32-bit prefix.', is_flag=True)
def mkwineprefix_main(
    prefix_name: str,
    prefix_root: str,
    vd: str = 'off',
    windows_version: WineWindowsVersion = 'xp',
    *,
    _32bit: bool = False,
    debug: bool = False,
    no_xdg: bool = False,
    sandbox: bool = False,
) -> None:
    """
    Create a Wine prefix with custom settings.
    
    This should be used with eval: eval $(mkwineprefix ...)
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    try:
        target = create_wine_prefix(prefix_name,
                                    _32bit=_32bit,
                                    debug=debug,
                                    no_xdg=no_xdg,
                                    prefix_root=prefix_root,
                                    sandbox=sandbox,
                                    vd=vd,
                                    windows_version=windows_version)
    except FileExistsError as e:
        raise click.Abort from e
    wineprefix_env = quote(f'WINEPREFIX={target}')
    click.echo(f"""Run `export WINEPREFIX={target}` before running wine or use env:

env {wineprefix_env} wine ...

If you ran this with eval, your shell is ready.""",
               file=sys.stderr)
    click.echo(f'export {wineprefix_env}')
    click.echo(f'export PS1="{prefix_name}🍷$PS1"')


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filenames', nargs=-1)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
def mvid_rename_main(filenames: tuple[str, ...], *, debug: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    log = logging.getLogger(__name__)
    for filename in filenames:
        path = Path(filename).resolve(strict=True)
        if not path.is_dir():
            log.debug('Ignored: %s', path)
            continue
        try:
            src = path / f'{path.name.lower()}.mkv'
            target = (path / f'../{path.name}.mkv').resolve()
            log.debug('%s -> %s', src, target)
            src.rename(target)
            send2trash(path)
        except Exception as e:  # noqa: BLE001
            log.debug('Exception with file %s: %s', path, e)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-a',
              '--affiliation',
              default='owner',
              help='Affiliation. See REST API documentation for more information.')
@click.option('-b',
              '--base-url',
              default=github.Consts.DEFAULT_BASE_URL,
              help='Base URL for enterprise.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('--delay', type=float, default=120, help='Delay in seconds between attempts.')
@click.option('-u', '--username', default=getpass.getuser(), help='Username.')
def merge_dependabot_prs_main(base_url: str,
                              username: str,
                              affiliation: str = 'owner',
                              delay: int = 120,
                              *,
                              debug: bool = False) -> None:
    """Merge pull requests made by Dependabot on GitHub."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    if not (token := keyring.get_password('tmu-github-api', username)):
        click.echo('No token.', err=True)
        raise click.Abort
    while True:
        try:
            merge_dependabot_pull_requests(affiliation=affiliation, base_url=base_url, token=token)
            break
        except RuntimeError:
            click.echo(f'Sleeping for {delay} seconds.')
            sleep(delay)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filenames', type=click.Path(exists=True), nargs=-1)
@click.argument('target')
@click.option('-C', 'compress', is_flag=True, help='Enable compression.')
@click.option('-P', '--port', type=int, default=22, help='Port.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-i', '--key', 'key_filename', type=click.File('r'), help='Private key.')
@click.option('-t', '--timeout', type=float, default=2, help='Timeout in seconds.')
@click.option(
    '-p',
    'preserve',
    is_flag=True,
    help='Preserves modification times, access times, and file mode bits from the source file.')
@click.option('-y',
              '--dry-run',
              is_flag=True,
              help='Do not copy anything. Use with -d for testing.')
def smv_main(filenames: str,
             target: str,
             key_filename: str,
             port: int = 22,
             timeout: float = 2,
             *,
             compress: bool = False,
             debug: bool = False,
             dry_run: bool = False,
             preserve: bool = False) -> None:
    """
    Secure move.

    This is similar to scp but deletes the file or directory after successful copy.

    Always test with the --dry-run/-y option.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    username = target.split('@')[0] if '@' in target else None
    hostname = target.split(':')[0]
    target_dir_or_filename = target.split(':')[1]
    with SSHClient() as client:
        client.load_system_host_keys()
        client.connect(hostname,
                       port,
                       username,
                       compress=compress,
                       key_filename=key_filename,
                       timeout=timeout)
        for filename in filenames:
            secure_move_path(client,
                             filename,
                             target_dir_or_filename,
                             dry_run=dry_run,
                             preserve_stats=preserve)


def _upload_to_imgbb_xdg_install(context: click.Context, _: Any, value: str) -> None:
    prefix = str(Path('~/.local').expanduser()) if (value == '-' or not value) else value
    apps = Path(f'{prefix}/share/applications')
    apps.mkdir(parents=True, exist_ok=True)
    (apps / 'upload-to-imgbb.desktop').write_text("""[Desktop Entry]
Categories=Graphics;2DGraphics;RasterGraphics;
Exec=upload-to-imgbb %U
Icon=imgbb
Keywords=graphic;design;
MimeType=image/avif;image/gif;image/jpeg;image/png;image/webp
Name=Upload to ImgBB
StartupNotify=false
Terminal=false
TryExec=upload-to-imgbb
Type=Application
Version=1.0
""")
    r = requests.get('https://simgbb.com/images/favicon.png', timeout=5)
    icons_dir = Path(f'{prefix}/share/icons/hicolor/300x300')
    icons_dir.mkdir(parents=True, exist_ok=True)
    (icons_dir / 'imgbb.png').write_bytes(r.content)
    sp.run(('update-desktop-database', '-v', str(apps)), check=True)
    context.exit()


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filenames', type=click.Path(exists=True, dir_okay=False), nargs=-1)
@click.option('--api-key', help='API key.', metavar='KEY')
@click.option('--keyring-username', help='Keyring username override.', metavar='USERNAME')
@click.option('--no-browser', is_flag=True, help='Do not copy URL to clipboard.')
@click.option('--no-clipboard', is_flag=True, help='Do not copy URL to clipboard.')
@click.option('--no-gui', is_flag=True, help='Disable GUI interactions.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-t',
              '--timeout',
              type=float,
              default=5,
              help='Timeout in seconds.',
              metavar='TIMEOUT')
@click.option('--xdg-install',
              default=None,
              metavar='PATH',
              help=('Install .desktop file. Argument is the installation prefix such as /usr. Use '
                    '- to install to user XDG directory.'))
def upload_to_imgbb_main(filenames: tuple[str, ...],
                         api_key: str | None = None,
                         keyring_username: str | None = None,
                         timeout: float = 5,
                         xdg_install: str | None = None,
                         *,
                         debug: bool = False,
                         no_browser: bool = False,
                         no_clipboard: bool = False,
                         no_gui: bool = False) -> None:
    """
    Upload image to ImgBB.
    
    Get an API key at https://api.imgbb.com/ and set it with `keyring set imgbb "${USER}"`.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    if xdg_install:
        prefix = str(Path('~/.local').expanduser()) if xdg_install == '-' else xdg_install
        apps = Path(f'{prefix}/share/applications')
        apps.mkdir(parents=True, exist_ok=True)
        (apps / 'upload-to-imgbb.desktop').write_text("""[Desktop Entry]
Categories=Graphics;2DGraphics;RasterGraphics;
Exec=upload-to-imgbb %U
Icon=imgbb
Keywords=graphic;design;
MimeType=image/avif;image/gif;image/jpeg;image/png;image/webp
Name=Upload to ImgBB
StartupNotify=false
Terminal=false
TryExec=upload-to-imgbb
Type=Application
Version=1.0
    """)
        r = requests.get('https://simgbb.com/images/favicon.png', timeout=5)
        icons_dir = Path(f'{prefix}/share/icons/hicolor/300x300')
        icons_dir.mkdir(parents=True, exist_ok=True)
        (icons_dir / 'imgbb.png').write_bytes(r.content)
        sp.run(('update-desktop-database', '-v', str(apps)), check=True, capture_output=not debug)
        return
    kdialog = which('kdialog')
    show_gui = not no_gui and len(filenames) == 1 and kdialog
    try:
        for name in filenames:
            r = upload_to_imgbb(name,
                                api_key=api_key,
                                keyring_username=keyring_username,
                                timeout=timeout)
            if not show_gui:
                click.echo(r.json()['data']['url'])
    except HTTPError as e:
        if show_gui:
            assert kdialog is not None
            sp.run((kdialog, '--sorry', 'Failed to upload!'), check=False)
        click.echo('Failed to upload. Check API key!', err=True)
        raise click.Abort from e
    if r:
        url: str = r.json()['data']['url']
        if not no_clipboard:
            pyperclip.copy(url)
        if show_gui:
            click.echo(url)
            assert kdialog is not None
            sp.run((kdialog, '--title', 'Successfully uploaded', '--msgbox', url), check=False)
        elif not no_browser:
            webbrowser.open(url)
