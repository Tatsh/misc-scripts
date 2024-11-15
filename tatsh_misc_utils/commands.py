from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from shlex import quote, split
from shutil import which
from time import sleep
from typing import TYPE_CHECKING, Any, Literal, TextIO, TypeVar, cast, overload
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

from binaryornot.helpers import is_binary_string
from platformdirs import user_state_path
from requests import HTTPError
from send2trash import send2trash
from typing_extensions import override
import click
import keyring
import pyperclip
import requests
import yaml

from tatsh_misc_utils import naming

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
from .io import (
    SFVVerificationError,
    UnRAR,
    UnRARExtractionTestFailed,
    extract_gog,
    unpack_0day,
    unpack_ebook,
    verify_sfv,
)
from .media import (
    add_info_json_to_media_file,
    archive_dashcam_footage,
    cddb_query,
    create_static_text_video,
    ffprobe,
    get_info_json,
    hlg_to_sdr,
    rip_cdda_to_flac,
    supported_audio_input_formats,
)
from .string import (
    fullwidth_to_narrow,
    is_ascii,
    is_url,
    sanitize,
    slugify,
    underscorize,
    unix_path_to_wine,
)
from .system import (
    CHROME_DEFAULT_LOCAL_STATE_PATH,
    IS_LINUX,
    IS_WINDOWS,
    find_bluetooth_device_info_by_name,
    inhibit_notifications,
    patch_macos_bundle_info_plist,
    slug_rename,
    wait_for_disc,
)
from .typing import (
    ChromeLocalState,
    DecodeErrorsOption,
    INCITS38Code,
    ProbeDict,
    StreamDispositionDict,
)
from .ultraiso import (
    InsufficientArguments,
    run_ultraiso,
)
from .utils import (
    TIMES_RE,
    WineWindowsVersion,
    add_cdda_times,
    create_wine_prefix,
    kill_processes_by_name,
    secure_move_path,
)
from .www import (
    check_bookmarks_html_urls,
    generate_html_dir_tree,
    upload_to_imgbb,
    where_from,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO

CONTEXT_SETTINGS = {'help_option_names': ('-h', '--help')}
_T = TypeVar('_T', bound=str)
log = logging.getLogger(__name__)


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
@click.option('-d', '--debug', is_flag=True, help='Enable debug logging.')
def clean_old_kernels_and_modules_main(path: str = DEFAULT_KERNEL_LOCATION,
                                       modules_path: str = DEFAULT_MODULES_PATH,
                                       active_kernel_name: str = DEFAULT_ACTIVE_KERNEL_NAME,
                                       *,
                                       quiet: bool = False,
                                       debug: bool = False) -> None:
    """
    Remove inactive kernels and modules.

    By default, removes old Linux sources from /usr/src.
    """
    logging.basicConfig(level=logging.INFO if not debug else logging.DEBUG)
    for item in clean_old_kernels_and_modules(path, modules_path, active_kernel_name):
        log.info(item)


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
    except FileNotFoundError as e:
        click.echo('Is UltraISO installed?')
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
@click.option('-b', '--base-url', help='Base URL for enterprise.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-u', '--username', default=getpass.getuser(), help='Username (passed to keyring).')
def git_checkout_default_branch_main(username: str,
                                     base_url: str | None = None,
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
    from git import Repo  # noqa: PLC0415
    repo = Repo(search_parent_directories=True)
    default_branch = get_github_default_branch(repo=repo,
                                               base_url=base_url,
                                               token=token,
                                               origin_name=origin_name)
    next(b for b in repo.heads if b.name == default_branch).checkout()


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('origin_name', metavar='ORIGIN_NAME', default='origin')
@click.option('-b', '--base-url', help='Base URL for enterprise.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-u', '--username', default=getpass.getuser(), help='Username (passed to keyring).')
@click.option('-r',
              '--remote',
              is_flag=True,
              help='Rebase with the origin copy of the default branch.')
def git_rebase_default_branch_main(username: str,
                                   base_url: str | None = None,
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
    from git import Repo  # noqa: PLC0415
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
    from git import Repo  # noqa: PLC0415
    url = Repo(search_parent_directories=True).remote(name).url
    if re.search(r'^https?://', url):
        webbrowser.open(url)
        return
    webbrowser.open(convert_git_ssh_url_to_https(url))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('file', type=click.File('rb'), default=sys.stdin)
def is_bin_main(file: BytesIO) -> None:
    """
    Check if a file has binary contents.

    For this utility, 0 byte files do not count as binary.

    Exit code 0 means the file probably contains binary content.
    """
    if ((file.name and (p := Path(file.name)) and p.exists() and p.stat().st_size == 0)
            and is_binary_string(file.read(1024))):
        return
    raise click.exceptions.Exit(1)


@click.command(context_settings={**CONTEXT_SETTINGS, 'auto_envvar_prefix': 'UMPV'})
@click.option('-d', '--debug', is_flag=True)
@click.option('--mpv-command', default='mpv', help='mpv command including arguments.')
@click.argument('files', nargs=-1)
def umpv_main(files: Sequence[str], mpv_command: str = 'mpv', *, debug: bool = False) -> int:
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    fixed_files = ((p if is_url(p) else str(Path(p).resolve(strict=True))) for p in files)
    socket_path = str(user_state_path() / 'umpv-socket')
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
    try:
        from gi.overrides.GLib import GError, Variant  # noqa: PLC0415
        from gi.repository import GLib  # type: ignore[unused-ignore] # noqa: PLC0415
        from pydbus import SystemBus  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError) as e:
        click.echo('Imports are missing.', err=True)
        raise click.Abort from e
    loop = GLib.MainLoop()
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
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
    click.echo(fullwidth_to_narrow(file.read()), nl=False)


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
@click.option('--no-xdg', is_flag=True, help='Disable winemenubuilder.exe.')
@click.option('-T', '--trick', 'tricks', help='Add an argument for winetricks.', multiple=True)
@click.option('--32', '_32bit', help='Use 32-bit prefix.', is_flag=True)
def mkwineprefix_main(
    prefix_name: str,
    prefix_root: str,
    tricks: tuple[str, ...],
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
                                    tricks=tricks,
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
@click.option('-b', '--base-url', help='Base URL for enterprise.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('--delay', type=float, default=120, help='Delay in seconds between attempts.')
@click.option('-u', '--username', default=getpass.getuser(), help='Username.')
def merge_dependabot_prs_main(username: str,
                              affiliation: str = 'owner',
                              base_url: str | None = None,
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
    from paramiko import SSHClient  # noqa: PLC0415
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


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('args', nargs=-1)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-H', '--host', help='CDDB hostname.', metavar='HOST')
def cddb_query_main(args: tuple[str, ...], host: str | None = None, *, debug: bool = False) -> None:
    """
    Display a CDDB result in a simple JSON format.

    Does not handle if result is not an exact match.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    click.echo(json.dumps(cddb_query(' '.join(args), host=host)._asdict(), indent=2,
                          sort_keys=True))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-D',
              '--drive',
              default='/dev/sr0',
              help='Optical drive path.',
              type=click.Path(exists=True, dir_okay=False))
@click.option('-M',
              '--accept-first-cddb-match',
              is_flag=True,
              help='Accept the first CDDB match in case of multiple matches.')
@click.option('--album-artist', help='Album artist override.')
@click.option('--album-dir', help='Album directory name. Defaults to artist-album-year format.')
@click.option('--cddb-host', help='CDDB host.', default='gnudb.gnudb.org')
@click.option('--never-skip',
              help="Passed to cdparanoia's --never-skip=... option.",
              type=int,
              default=5)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-o',
              '--output-dir',
              help='Parent directory for album_dir. Defaults to current directory.')
@click.option('-u', '--username', default=getpass.getuser(), help='Username for CDDB.')
def ripcd_main(drive: str = '/dev/sr0',
               album_artist: str | None = None,
               album_dir: str | None = None,
               cddb_host: str | None = None,
               never_skip: int = 5,
               output_dir: str | None = None,
               username: str | None = None,
               *,
               accept_first_cddb_match: bool = True,
               debug: bool = False) -> None:
    """
    Rip an audio disc to FLAC files.

    Requires cdparanoia and flac to be in PATH.

    For Linux only.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    try:
        rip_cdda_to_flac(drive,
                         accept_first_cddb_match=accept_first_cddb_match,
                         album_artist=album_artist,
                         album_dir=album_dir,
                         cddb_host=cddb_host,
                         never_skip=never_skip,
                         output_dir=output_dir,
                         username=username)
    except (sp.CalledProcessError, requests.RequestException, ValueError) as e:
        click.echo(str(e), err=True)
        raise click.Abort from e


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('files', nargs=-1)
@click.option('-A', '--album', help='Album.')
@click.option('-D',
              '--delete-all-before',
              is_flag=True,
              help='Delete all existing tags before processing.')
@click.option('-T', '--track', type=int, help='Track number.')
@click.option('-a', '--artist', help='Track artist.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-g', '--genre', help='Genre.')
@click.option('-p', '--picture', help='Cover artwork to attach.')
@click.option('-t', '--title', help='Track title.')
@click.option('-y', '--year', type=int, help='Year.')
def flacted_main(files: tuple[str, ...],
                 album: str | None = None,
                 artist: str | None = None,
                 genre: str | None = None,
                 picture: str | None = None,
                 title: str | None = None,
                 track: int | None = None,
                 year: int | None = None,
                 *,
                 debug: bool = False,
                 delete_all_before: bool = False) -> None:
    """Front-end to metaflac to set common tags."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)

    def metaflac(*args: Any, **kwargs: Any) -> sp.CompletedProcess[str]:
        return sp.run(('metaflac', *cast(tuple[str, ...], args)),
                      capture_output=not debug,
                      **kwargs,
                      check=True,
                      text=True)

    invoked_as = Path(sys.argv[0]).name
    if invoked_as != 'flacted' and len(files) > 0:
        tag_requested = invoked_as.split('-')[1].lower()
        possible: tuple[str, ...] = (tag_requested.title(), tag_requested.upper(), tag_requested)
        if tag_requested.lower() == 'year':
            possible += ('Date', 'DATE', 'date')
        unfiltered_files = files
        filtered_files = []
        for file in unfiltered_files:
            with contextlib.suppress(FileNotFoundError):
                filtered_files.append(str(Path(file).resolve(strict=True)))
        show_filename = len(files) > 1
        for filename in files:
            for tag in possible:
                val = metaflac(f'--show-tag={tag}', filename).stdout.strip()
                try:
                    val = val[len(tag) + 1:].splitlines()[0].strip()
                except IndexError:
                    val = ''
                if val:
                    if tag_requested == 'track':
                        try:
                            val_int: int | None = int(val)
                        except TypeError:
                            val = ''
                            val_int = None
                        if val_int:
                            val = f'{val_int:02d}'
                    if show_filename:
                        click.echo(f'{filename}: {val}')
                    else:
                        click.echo(f'{val}')
                    break
        return
    min_args = 3
    metaflac_args = ['--preserve-modtime', '--no-utf8-convert']
    clean_up_args = metaflac_args.copy()
    destroy = delete_all_before
    clean_up_args.append('--remove-all-tags')
    clean_up_args.extend(files)
    for key, value in {
            'album': album,
            'artist': artist,
            'genre': genre,
            'title': title,
            'track': track,
            'year': year
    }.items():
        if not value:
            continue
        value_ = value.strip() if isinstance(value, str) else value
        match key:
            case 'year':
                flac_tag = 'Date'
            case 'track':
                flac_tag = 'Tracknumber'
            case _:
                flac_tag = f'{key[0].upper()}{key[1:]}'
        metaflac_args.append(f'--set-tag={flac_tag}={value_}')
    if picture:
        metaflac_args.append(f'--import-picture-from={picture}')
    if len(metaflac_args) < min_args:
        click.echo('Not doing anything', err=True)
        raise click.Abort
    if destroy:
        metaflac(*clean_up_args)
    metaflac_args.extend(files)
    metaflac(*metaflac_args)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('paths', type=click.Path(exists=True, file_okay=False), nargs=-1)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-D', '--delete-paths', help='Delete paths after extraction.', is_flag=True)
def ke_ebook_ex_main(paths: str, *, debug: bool = False, delete_paths: bool = False) -> None:
    """Extract ebooks from RARs within Zip files."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    for path in paths:
        unpack_ebook(path)
    if delete_paths:
        for path in paths:
            send2trash(path)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('bundle', type=click.Path(dir_okay=True, file_okay=False))
@click.option('-E',
              '--env-var',
              'env_vars',
              help='Environment variable to set.',
              multiple=True,
              type=(str, str))
@click.option('-r', '--retina', type=int, help='For macOS apps, force Retina support.')
def patch_bundle_main(bundle: str,
                      env_vars: tuple[tuple[str, str], ...],
                      *,
                      retina: bool = False) -> None:
    """Patch a macOS/iOS/etc bundle's Info.plist file."""
    data: dict[str, Any] = {}
    if env_vars:
        data['LSEnvironment'] = dict(env_vars)
    if retina:
        data['NSHighResolutionCapable'] = True
    patch_macos_bundle_info_plist(bundle, **data)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filename', type=click.Path(exists=True, dir_okay=False))
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-o',
              '--output-dir',
              default='.',
              type=click.Path(exists=True, file_okay=False),
              help='Output directory.')
def gogextract_main(filename: str, output_dir: str, *, debug: bool = False) -> None:
    """Extract a Linux gog.com archive."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.ERROR)
    extract_gog(filename, output_dir)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filename', type=click.Path(exists=True, dir_okay=False))
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-o', '--output-file', type=click.File('w'), default=sys.stdout)
def check_bookmarks_html_main(filename: str, output_file: TextIO, *, debug: bool = False) -> None:
    """Check for URLs that are not valid any more (status 404) and redirections."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    _, changed, not_found = check_bookmarks_html_urls(Path(filename).read_text(encoding='utf-8'))
    click.echo(f'{len(changed)} URLS changed.')
    click.echo(f'{len(not_found)} URLS resulted in 404 response.')


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('front_dir', type=click.Path(exists=True, dir_okay=True))
@click.argument('rear_dir', type=click.Path(exists=True, dir_okay=True))
@click.argument('output_dir', type=click.Path(dir_okay=True), default='.')
@click.option('--clip-length', help='Clip length in minutes.', type=int, default=3)
@click.option('--hwaccel', help='-hwaccel string for ffmpeg.', default='auto')
@click.option('--level', help='Level (HEVC).', type=int, default=5)
@click.option('--no-fix-groups', help='Disable group discrepancy resolution.', is_flag=True)
@click.option('--no-hwaccel', help='Disable hardware decoding.', is_flag=True)
@click.option('--no-rear-crop', is_flag=True, help='Disable rear video cropping.')
@click.option('--no-setpts', is_flag=True, help='Disable use of setpts.')
@click.option('--preset', help='Output preset (various codecs).', default='p5')
@click.option('--rear-crop', default='1920:1020:0:0', help='Crop string for the rear camera view.')
@click.option('--rear-view-scale-divisor',
              default=2.5,
              type=float,
              help='Scaling divisor for rear view.')
@click.option('--setpts',
              help='setpts= string. Defaults to speeding video by 4x.',
              default='0.25*PTS')
@click.option('--tier', help='Tier (HEVC).', default='high')
@click.option('--time-format',
              metavar='FORMAT',
              help='Time format to parse from video files.',
              default='%Y%m%d%H%M%S')
@click.option('--video-bitrate', default='0k', help='Video bitrate.', metavar='BITRATE')
@click.option('--video-decoder',
              default='hevc_cuvid',
              help='Video decoder (for hardware decoding only).',
              metavar='DECODER')
@click.option('--video-encoder', default='hevc_nvenc', help='Video encoder.', metavar='ENCODER')
@click.option('--video-max-bitrate',
              default='15M',
              help='Maximum video bitrate.',
              metavar='BITRATE')
@click.option('-M',
              '--match-regexp',
              help='Regular expression to find the date string.',
              default=r'^(\d+)_.*',
              metavar='RE')
@click.option('-O', '--overwrite', is_flag=True, help='Overwrite existing files.')
@click.option('-T', '--temp-dir', help='Temporary directory for processing.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
def encode_dashcam_main(front_dir: str,
                        rear_dir: str,
                        output_dir: str,
                        clip_length: int = 3,
                        hwaccel: str = 'auto',
                        level: int = 5,
                        match_regexp: str = r'^(\d+)_.*',
                        preset: str = 'p5',
                        rear_crop: str = '1920:1020:0:0',
                        rear_view_scale_divisor: float = 2.5,
                        setpts: str = '0.25*PTS',
                        temp_dir: str | None = None,
                        tier: str = 'high',
                        time_format: str = '%Y%m%d%H%M%S',
                        video_bitrate: str = '0k',
                        video_decoder: str = 'hevc_cuvid',
                        video_encoder: str = 'hevc_nvenc',
                        video_max_bitrate: str = '15M',
                        *,
                        debug: bool = False,
                        no_fix_groups: bool = False,
                        no_hwaccel: bool = False,
                        no_rear_crop: bool = False,
                        no_setpts: bool = False,
                        overwrite: bool = False) -> None:
    """
    Batch encode dashcam footage, merging rear and front camera footage.
    
    This command's defaults are intended for use with Red Tiger dashcam output and file structure.

    The rear camera view will be placed in the bottom right of the video scaled by dividing the
    width and height by the --rear-view-scale-divisor value specified. It will also be cropped using
    the --rear-crop value unless --no-rear-crop is passed.
    
    Files are automatically grouped using the regular expression passed with -M/--match-regexp. This
    RE must contain at least one group and only the first group will be considered. Make dubious use
    of non-capturing groups if necessary. The captured group string is expected to be usable with
    the time format specified with --time-format (see strptime documentation at
    https://docs.python.org/3/library/datetime.html#datetime.datetime.strptime).
    
    In many cases, the camera leaves behind stray rear camera files (usually no more than one per
    group and always a video without a matching front video file the end). These are automatically
    ignored if possible. This behaviour can be disabled by passing --no-fix-groups.

    Original files' whose content is successfully converted are sent to the wastebin.

    Example use:
    
        encode-dashcam Movie_F/ Movie_R/ ~/output_dir
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    if Path(front_dir).resolve(strict=True) == Path(rear_dir).resolve(strict=True):
        click.echo('Front and rear directories are the same.', err=True)
        raise click.Abort
    archive_dashcam_footage(front_dir,
                            rear_dir,
                            output_dir,
                            allow_group_discrepancy_resolution=not no_fix_groups,
                            clip_length=clip_length,
                            hwaccel=None if no_hwaccel else hwaccel,
                            level=level,
                            match_re=match_regexp,
                            overwrite=overwrite,
                            preset=preset,
                            rear_crop=None if no_rear_crop else rear_crop,
                            rear_view_scale_divisor=rear_view_scale_divisor,
                            setpts=None if no_setpts else setpts,
                            temp_dir=temp_dir,
                            tier=tier,
                            time_format=time_format,
                            video_bitrate=video_bitrate,
                            video_decoder=video_decoder,
                            video_encoder=video_encoder,
                            video_max_bitrate=video_max_bitrate)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('rar_filename', type=click.Path(dir_okay=False, exists=True))
@click.option('--no-crc-check', is_flag=True, help='Disable CRC check.')
@click.option('--test-extraction', help='Enable extraction test.', is_flag=True)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-D',
              '--device-name',
              help='Device name.',
              type=click.Path(exists=True, dir_okay=False))
@click.option('-s', '--speed', type=int, help='Disc write speed.', default=8)
@click.option('--sfv', help='SFV file.', type=click.Path(exists=True, dir_okay=False))
@click.option('--cdrecord-path', help='Path to cdrecord.', default='cdrecord')
@click.option('--unrar-path', help='Path to unrar.', default='unrar')
def burnrariso_main(rar_filename: str,
                    unrar_path: str = 'unrar',
                    cdrecord_path: str = 'cdrecord',
                    device_name: str | None = None,
                    sfv: str | None = None,
                    speed: int = 8,
                    *,
                    debug: bool = False,
                    no_crc_check: bool = False,
                    test_extraction: bool = False) -> None:
    """Burns an ISO found in a RAR file via piping."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    rar_path = Path(rar_filename)
    unrar = UnRAR(unrar_path)
    isos = [x for x in unrar.list_files(rar_path) if x.name.lower().endswith('.iso')]
    if len(isos) != 1:
        raise click.Abort
    iso = isos[0]
    if not iso.size:
        raise click.Abort
    if not no_crc_check:
        sfv_file_expected = (Path(sfv) if sfv else rar_path.parent /
                             f'{rar_path.name.split(".", 1)}.sfv')
        assert sfv_file_expected.exists()
        try:
            verify_sfv(sfv_file_expected)
        except SFVVerificationError as e:
            click.echo('SFV verification failed.', err=True)
            raise click.Abort from e
    if test_extraction:
        click.echo('Testing extraction.')
        try:
            unrar.test_extraction(rar_path, iso.name)
        except UnRARExtractionTestFailed:
            click.echo('RAR extraction test failed.', err=True)
    with (unrar.pipe(rar_filename, iso.name) as u,
          sp.Popen(
              (cdrecord_path, *((f'dev={device_name}',) if device_name else
                                ()), f'speed={speed}', 'driveropts=burnfree', f'tsize={iso.size}'),
              stdin=u.stdout,
              close_fds=True) as cdrecord):
        assert u.stdout is not None
        u.stdout.close()
        cdrecord.wait()
        u.wait()
        if not (u.returncode == 0 and cdrecord.returncode == 0):
            click.echo('Write failed!', err=True)
            raise click.Abort


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('titles', type=click.File('r'), default=sys.stdin)
@click.option('--no-names', help='Disable name checking.', is_flag=True)
@click.option('-E', '--no-english', help='Disable English mode.', is_flag=True)
@click.option('-a', '--arabic', help='Enable Arabic mode.', is_flag=True)
@click.option('-c', '--chinese', help='Enable Chinese mode.', is_flag=True)
@click.option('-j', '--japanese', help='Enable Japanese mode.', is_flag=True)
@click.option('-s', '--ampersands', help='Replace " and " with " & ".', is_flag=True)
def title_fixer_main(titles: tuple[str, ...],
                     *,
                     no_english: bool = False,
                     chinese: bool = False,
                     japanese: bool = False,
                     arabic: bool = False,
                     no_names: bool = False,
                     ampersands: bool = False) -> None:
    modes = (
        *((naming.Mode.Arabic,) if arabic else ()),
        *((naming.Mode.Chinese,) if chinese else ()),
        *((naming.Mode.English,) if not no_english else ()),
        *((naming.Mode.Japanese,) if japanese else ()),
    )
    if not modes:
        click.echo('No modes specified.', err=True)
        raise click.Abort
    for title in titles:
        click.echo(naming.adjust_title(title, modes, disable_names=no_names, ampersands=ampersands))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('local_state_path',
                type=click.Path(dir_okay=False, exists=True),
                metavar='LOCAL_STATE_PATH',
                default=CHROME_DEFAULT_LOCAL_STATE_PATH)
@click.option('-s',
              '--subprocess-name',
              default='chrome' if not IS_WINDOWS else 'chrome.exe',
              help='Chromium-based browser subprocess name such as "chrome"')
@click.option('--sleep-time',
              default=0.5,
              type=float,
              help='Time to sleep after attempting to kill the browser processes in seconds.')
def chrome_bisect_flags_main(local_state_path: str,
                             subprocess_name: str = 'chrome',
                             sleep_time: float = 0.5) -> None:
    """
    Determine which flag is causing an issue in Chrome or any Chromium-based browser.

    Only supports removing flags (setting back to default) and not setting them to 'safe' values.
    """
    flags_min_len = 2

    def start_test(flags: Sequence[str], local_state: ChromeLocalState) -> tuple[bool, str | None]:
        """
        Test apparatus.

        Returns ``True`` if:
        - there are no more flags (problem flag not found)
        - if there is only one flag left (problem flag possibly found)
        - if the problematic flag exists within the passed in flags
        """
        len_flags = len(flags)
        if len_flags == 0:
            click.echo('Could not find the problem flag.')
            return True, None
        click.echo('Testing flags:')
        for flag in flags:
            click.echo(f'- {flag}')
        local_state['browser']['enabled_labs_experiments'] = flags
        with Path(local_state_path).open('w+', encoding='utf-8') as f:
            json.dump(local_state, f, allow_nan=False)
        click.confirm('Start browser and test for the issue, then press enter', show_default=False)
        kill_processes_by_name(subprocess_name, sleep_time, force=True)
        at_fault = click.confirm('Did the problem occur?')
        return at_fault, flags[0] if at_fault and len_flags == 1 else None

    def do_test(flags: Sequence[str], local_state: ChromeLocalState) -> str | None:
        len_flags = len(flags)
        if len_flags < flags_min_len:
            return flags[0] if len_flags == 1 else None
        done, bad_flag = start_test(flags[:len_flags // 2], deepcopy(local_state))
        if done:
            return bad_flag or do_test(flags[:len_flags // 2], local_state)
        done, bad_flag = start_test(flags[len_flags // 2:], deepcopy(local_state))
        if done:
            return bad_flag or do_test(flags[len_flags // 2:], local_state)
        return None

    p_ls = Path(local_state_path).resolve(strict=True)
    click.echo(f'Using "{local_state_path}".')
    with p_ls.open(encoding='utf-8') as f:
        local_state_data = json.load(f)
        flags = local_state_data['browser']['enabled_labs_experiments']
        len_flags = len(flags)
        if len_flags == 0:
            click.echo('Nothing to test.', err=True)
            raise click.Abort
    bad_flag = None
    try:
        click.confirm('Exit the browser and press enter', show_default=False)
        bad_flag = do_test(flags, local_state_data)
    except KeyboardInterrupt as e:
        raise click.Abort from e
    finally:
        if bad_flag:
            local_state_data['browser']['enabled_labs_experiments'] = [
                x for x in local_state_data['browser']['enabled_labs_experiments'] if x != bad_flag
            ]
        with p_ls.open('w+', encoding='utf-8') as f:
            json.dump(local_state_data, f, sort_keys=True, indent=2, allow_nan=False)
        if not bad_flag:
            click.echo('Restored original "Local State".')
        else:
            click.echo(f'Saved "Local State" with "{bad_flag}" removed.')


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filenames', type=click.Path(exists=True, dir_okay=False), nargs=2)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
def mpv_sbs_main(filenames: tuple[str, str],
                 max_width: int = 3840,
                 min_height: int = 31,
                 min_width: int = 31,
                 *,
                 debug: bool = False) -> None:
    @overload
    def get_prop(prop: Literal['codec_type'], info: ProbeDict) -> Literal['audio', 'video']:
        ...

    @overload
    def get_prop(prop: Literal['disposition'], info: ProbeDict) -> StreamDispositionDict:
        ...

    @overload
    def get_prop(prop: Literal['height', 'width'], info: ProbeDict) -> int:
        ...

    def get_prop(prop: Literal['codec_type', 'disposition', 'height', 'width'],
                 info: ProbeDict) -> Literal['audio', 'video'] | StreamDispositionDict | int:
        return max((x for x in info['streams'] if x['codec_type'] == 'video'),
                   key=lambda x: x['disposition'].get('default', 0))[prop]

    def get_default_video_index(info: ProbeDict) -> int:
        for i, x in enumerate(info['streams']):
            try:
                if x['disposition']['default']:
                    return i
            except (KeyError, IndexError):
                continue
        return next((i for i, x in enumerate(info['streams']) if x['codec_type'] == 'video'), 0)

    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    filename1, filename2 = filenames
    info1, info2 = ffprobe(filename1), ffprobe(filename2)
    width1, width2 = (int(get_prop('width', info1)), int(get_prop('width', info2)))
    height1, height2 = (int(get_prop('height', info1)), int(get_prop('height', info2)))
    assert height1 > min_height, 'Invalid height in video 1'
    assert height2 > min_height, 'Invalid height in video 2'
    assert width1 <= max_width, 'Video 1 is too wide'
    assert width1 > min_width, 'Invalid width in video 1'
    assert width2 <= max_width, 'Video 2 is too wide'
    assert width2 > min_width, 'Invalid width in video 2'
    scale_w = max(width1, width2)
    scale_h = int(get_prop('height', info1)) if scale_w == width1 else int(get_prop(
        'height', info2))
    scale = '' if width1 == width2 and height1 == height2 else f'scale={scale_w}x{scale_h}'
    scale1, scale2 = (scale if scale_h != height1 == 1 else '',
                      scale if scale_h == height1 == 2 else '')  # noqa: PLR2004
    second_stream_index = (len([x for x in info1['streams'] if x['codec_type'] == 'video']) +
                           get_default_video_index(info2)) + 1
    if not scale1 and not scale2:
        filter_chain = '[vid1][vid2] hstack [vo]'
    else:
        filter_chain = ';'.join(
            (f'[vid1] {scale} [vid1_scale]',
             f'[vid{second_stream_index}] {scale} [vid{second_stream_index}_crop]',
             f'[vid1_scale][vid{second_stream_index}_crop] hstack [vo]'))
    cmd = ('mpv', '--hwdec=no', '--config=no', filename1, f'--external-file={filename2}',
           f'--lavfi-complex={filter_chain}')
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    sp.run(cmd, check=True)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filename', type=click.Path(exists=True, dir_okay=False))
@click.argument('output', type=click.Path(dir_okay=False), required=False)
@click.option('--codec',
              help='Video codec.',
              type=click.Choice(('libx264', 'libx265')),
              default='libx265')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('--crf', help='CRF value.', type=int, default=20)
@click.option('--delete-after', help='Send processed file to wastebin.', is_flag=True)
@click.option('-f', '--fast', help='Use less filters (lower quality).', is_flag=True)
def hlg2sdr_main(filename: str,
                 output: str | None,
                 crf: int = 20,
                 codec: Literal['libx264', 'libx265'] = 'libx265',
                 *,
                 debug: bool = False,
                 delete_after: bool = False,
                 fast: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    hlg_to_sdr(filename, crf, codec, output, fast=fast, delete_after=delete_after)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('filename', type=click.Path(exists=True, dir_okay=False))
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('--input-json', help='Input JSON file.', type=click.Path(exists=True, dir_okay=False))
def tbc2srt_main(filename: str, input_json: str | None = None, *, debug: bool = False) -> None:
    """
    Convert VBI data in a ld-decode/vhs-decode TBC file to SubRip format.
    
    Requires the following:
        * ld-process-vbi
        * ld-export-metadata
        * scc2raw.pl
        * ccextractor
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    p_filename = Path(filename)
    scc_file = p_filename.parent / f'{p_filename.stem}.scc'
    bin_file = p_filename.parent / f'{p_filename.stem}.bin'
    output_json_file = p_filename.parent / f'{p_filename.stem}.json'
    input_json = input_json or str(p_filename.parent / 'input.json')
    cmd: tuple[str, ...] = ('ld-process-vbi', '--input-json', input_json, '--output-json',
                            str(output_json_file), filename)
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    sp.run(cmd, check=True)
    cmd = ('ld-export-metadata', '--closed-captions', str(scc_file), str(output_json_file))
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    sp.run(cmd, check=True)
    cmd = ('scc2raw.pl', str(scc_file))
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    sp.run(cmd, check=True)
    cmd = ('ccextractor', '-in=raw', str(bin_file))
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    sp.run(cmd, check=True)
    send2trash([scc_file, bin_file, output_json_file, input_json])
