from collections.abc import Iterable
from pathlib import Path
from shlex import quote
from typing import Literal, TypedDict
import logging
import os
import subprocess as sp
import typing

from .string import unix_path_to_wine
from .system import IS_WINDOWS
from .typing import StrPath, UNIXStrPath, contains_type_path_like_str

__all__ = ('NOT_ENOUGH_ARGUMENTS_EXIT_CODE', 'BatchOptions', 'BootOptions', 'DirOptions',
           'FSOptions', 'HideOptions', 'ISZOptions', 'InfoOptions', 'OperationOptions',
           'SettingsOptions', 'UNIXStrPath', 'run_ultraiso')

DEFAULT_WINE_PREFIX = Path.home() / '.local/share/wineprefixes/ultraiso'
MIN_ARGUMENTS = 4 if not IS_WINDOWS else 3
NOT_ENOUGH_ARGUMENTS_EXIT_CODE = 99
log = logging.getLogger(__name__)


class InfoOptions(TypedDict, total=False):
    """Options pertaining to information stored in the image file."""
    appid: str | None
    """Application ID."""
    preparer: str | None
    """Preparer name."""
    publisher: str | None
    """Publisher name."""
    sysid: str | None
    """System ID."""
    volset: int | None
    """Volume set ID."""
    volume: str | None
    """Volume label."""


class SettingsOptions(TypedDict, total=False):
    """Options pertaining to processing."""
    ilong: bool
    """Long filename for ISO 9660 volume, up to 31 characters."""
    imax: bool
    """Max filename for ISO 9660 volume, up to 207 characters."""
    lowercase: bool
    """Allow lowercase letters."""
    vernum: bool
    """Include file version number."""


class FSOptions(TypedDict, total=False):
    """Options pertaining to file systems on the image."""
    hfs: bool
    """Create Apple HFS volume."""
    jlong: bool
    """Long filenames for joliet volume, up to 103 characters."""
    joliet: bool
    """Create a Joliet volume."""
    rockridge: bool
    """Create RockRidge volume."""
    udf: bool
    """Create UDF volume."""
    udfdvd: bool
    """Create UDF DVD image (this option will overwrite all other volume settings)."""


class BootOptions(TypedDict, total=False):
    """Options pertaining to bootable images."""
    bootfile: UNIXStrPath | None
    """Boot file."""
    bootinfotable: bool
    """Generate boot information table in boot file."""
    optimize: bool
    """Optimize file systems by coding same files only once."""


class DirOptions(TypedDict, total=False):
    """Options pertaining to directories."""
    chdir: str | None
    """Change current directory in ISO image."""
    newdir: str | None
    """Create a new directory."""
    rmdir: str | None
    """Remove a file or folder from ISO image (full path should be specified)."""


class HideOptions(TypedDict, total=False):
    """Options pertaining to hidden files."""
    ahide: str | None
    """Set advanced hidden attribute of a file or folder (full path should be specified)."""
    hide: str | None
    """Set hidden attribute of a file or folder (full path should be specified)."""
    pn: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9] | None
    """Set priority of a file or folder(full path should be specified)."""


class BatchOptions(TypedDict, total=False):
    """Options pertaining to conversion to ISO."""
    bin2iso: UNIXStrPath | None
    """Convert input CD/DVD image to ISO format."""
    dmg2iso: UNIXStrPath | None
    """Convert input DMG image to ISO format."""


class ISZOptions(TypedDict, total=False):
    """Options pertaining to creating UltraISO-specific ISZ files."""
    bin2isz: UNIXStrPath | None
    """Convert image to ISZ."""
    compress: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16] | None
    """Set compression level."""
    encrypt: Literal[1, 2, 3] | None
    """Set encryption method."""
    password: str | None
    """Set password."""
    split: int | None
    """Set segment size in bytes."""


class OperationOptions(TypedDict, total=False):
    """Options for simple operations."""
    extract: UNIXStrPath | None
    """Extract ISO image to specified directory."""
    get: str | None
    """Set a file or directory (full path) to be extracted."""
    list: UNIXStrPath | None
    """Create a list of files and directores in an ISO image."""


def get_ultraiso_path(prefix: StrPath) -> StrPath | None:
    program_files_paths = [f'Program Files{x}/UltraISO/UltraISO.exe' for x in ('', ' (x86)')]
    prefix = Path(prefix) / 'drive_c' if not IS_WINDOWS else Path('C:/')
    for exe in (prefix / x for x in program_files_paths):
        if exe.exists():
            return exe
    return None


def assert_is_file(path: UNIXStrPath) -> None:
    assert Path(path).is_file()


def run_ultraiso(
        *,
        add_dirs: Iterable[UNIXStrPath] | None = None,
        add_files: Iterable[UNIXStrPath] | None = None,
        batch: BatchOptions | None = None,
        boot: BootOptions | None = None,
        cmd: UNIXStrPath | None = None,
        dir: DirOptions | None = None,  # noqa: A002
        fs: FSOptions | None = None,
        hide: HideOptions | None = None,
        info: InfoOptions | None = None,
        input: UNIXStrPath | None = None,  # noqa: A002
        isz: ISZOptions | None = None,
        ops: OperationOptions | None = None,
        output: UNIXStrPath | None = None,
        prefix: StrPath = DEFAULT_WINE_PREFIX,
        settings: SettingsOptions | None = None) -> tuple[int, str]:
    """
    Run UltraISO in a convenient way.

    Despite always passing ``-silent`` to the application, windows may still appear.

    On non-Windows, for any option taking a file path, only pass UNIX file paths. They will be
    converted as needed.
    """
    if (actual_exe_path := get_ultraiso_path(prefix)) is None:
        raise FileNotFoundError
    env = {}
    if not IS_WINDOWS:
        env = {'WINEPREFIX': str(prefix), 'HOME': os.environ['HOME']}
        if 'DISPLAY' not in os.environ or 'XAUTHORITY' not in os.environ:
            log.warning(
                'UltraISO.exe will likely fail to run since DISPLAY or XAUTHORITY are not in '
                'the environment.')
        env['DISPLAY'] = os.environ.get('DISPLAY', '')
        env['XAUTHORITY'] = os.environ.get('XAUTHORITY', '')
    sp_args: list[str] = ['wine'] if not IS_WINDOWS else []
    sp_args += [str(actual_exe_path), '-silent']
    for key, filename in (('-cmd', cmd), ('-in', input), ('-out', output)):
        if filename:
            assert_is_file(filename)
            sp_args += [key, unix_path_to_wine(filename)]
    for file in (add_files or []):
        sp_args += ['-file', unix_path_to_wine(file)]
    for dir_ in (add_dirs or []):
        sp_args += ['-directory', str(dir_)]
    for args, dict_type in ((batch, BatchOptions), (boot, BootOptions), (dir, DirOptions),
                            (fs, FSOptions), (hide, HideOptions), (info, InfoOptions),
                            (isz, ISZOptions), (ops, OperationOptions), (settings,
                                                                         SettingsOptions)):
        if not args:
            continue
        for k, v in args.items():
            if isinstance(v, bool) and v:
                sp_args += [f'-{k}']
            elif (isinstance(v, str)
                  and contains_type_path_like_str(typing.get_type_hints(dict_type)[k])):
                sp_args += [f'-{k}', unix_path_to_wine(v)]
            elif v is not None and not isinstance(v, bool):
                sp_args += [f'-{k}', str(v)]
    if len(sp_args) < MIN_ARGUMENTS:
        log.error('Not enough arguments.')
        return NOT_ENOUGH_ARGUMENTS_EXIT_CODE, ''
    quoted_args = ' '.join(quote(x) for x in sp_args)
    if not IS_WINDOWS:
        log.debug('Command: env %s %s', quote(f'WINEPREFIX={prefix}'), quoted_args)
    else:
        log.debug('Command: %s', quoted_args)
    process = sp.run(sp_args, capture_output=True, env=env, text=True, check=False)
    stderr = process.stderr.strip()
    if process.returncode != 0 and stderr:
        log.error('stderr output:')
        for line in stderr.splitlines():
            if (not IS_WINDOWS and ('winemenubuilder.exe' in line or 'fixme:' in line
                                    or 'wine: using fast synchronization.' in line)):
                continue
            log.error(' -> %s', line)
            return process.returncode, ''
    return process.returncode, process.stdout
