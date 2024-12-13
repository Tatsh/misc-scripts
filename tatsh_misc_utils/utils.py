"""Uncategorised utilities."""
from __future__ import annotations

from io import BytesIO
from math import trunc
from os import environ
from pathlib import Path
from shlex import quote
from shutil import copyfile, which
from signal import SIGTERM
from typing import TYPE_CHECKING, Literal, overload
import csv
import logging
import os
import re
import subprocess as sp
import tarfile
import time

import requests
import xz

from .media import CD_FRAMES
from .system import IS_WINDOWS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from paramiko import SFTPClient, SSHClient

    from .typing import StrPath

__all__ = ('WineWindowsVersion', 'add_cdda_times', 'create_wine_prefix', 'secure_move_path')

ZERO_TO_59 = '|'.join(f'{x:02d}' for x in range(60))
ZERO_TO_74 = '|'.join(f'{x:02d}' for x in range(75))
TIMES_RE = re.compile(f'^({ZERO_TO_59}):({ZERO_TO_59}):({ZERO_TO_74})$')
MAX_MINUTES = 99
MAX_SECONDS = 60
log = logging.getLogger(__name__)


def add_cdda_times(times: Iterable[str] | None) -> str | None:
    if not times:
        return None
    total_ms = 0.0
    for time_ in times:
        if not (res := re.match(TIMES_RE, time_)):
            return None
        minutes, seconds, frames = [float(x) for x in res.groups()]
        total_ms += (minutes *
                     (MAX_SECONDS - 1) * 1000) + (seconds * 1000) + (frames * 1000) / CD_FRAMES
    minutes = total_ms / (MAX_SECONDS * 1000)
    remainder_ms = total_ms % (MAX_SECONDS * 1000)
    seconds = remainder_ms / 1000
    remainder_ms %= 1000
    frames = (remainder_ms * 1000 * CD_FRAMES) / 1e6
    if minutes > MAX_MINUTES or seconds > (MAX_SECONDS - 1) or frames > CD_FRAMES:
        return None
    return f'{trunc(minutes):02d}:{trunc(seconds):02d}:{trunc(frames):02d}'


WineWindowsVersion = Literal['11', '10', 'vista', '2k3', '7', '8', 'xp', '81', '2k', '98', '95']
WINETRICKS_VERSION_MAPPING = {
    '11': 'win10',
    '10': 'win10',
    'vista': 'vista',
    '2k3': 'win2k3',
    '7': 'win7',
    '8': 'win8',
    'xp': 'winxp',
    '81': 'win81',
    # 32-bit only
    '2k': 'win2k',
    '98': 'win98',
    '95': 'win95'
}

DEFAULT_DPI = 96


def create_wine_prefix(prefix_name: str,
                       *,
                       _32bit: bool = False,
                       dpi: int = DEFAULT_DPI,
                       dxva_vaapi: bool = False,
                       dxvk_nvapi: bool = False,
                       eax: bool = False,
                       gtk: bool = False,
                       no_xdg: bool = False,
                       prefix_root: StrPath | None = None,
                       sandbox: bool = False,
                       tricks: Iterable[str] | None = None,
                       vd: str = 'off',
                       windows_version: WineWindowsVersion = 'xp',
                       winrt_dark: bool = False) -> StrPath:
    """
    Create a Wine prefix with custom settings.

    Requires Wine and winetricks.
    """
    tricks = list((t for t in tricks
                   if t not in WINETRICKS_VERSION_MAPPING.values() and not t.startswith('vd=')
                   ) if tricks else [])
    prefix_root = Path(prefix_root) if prefix_root else Path.home() / '.local/share/wineprefixes'
    prefix_root.mkdir(parents=True, exist_ok=True)
    target = prefix_root / prefix_name
    if target.exists():
        raise FileExistsError
    arch = 'win32' if _32bit else None
    if 'DISPLAY' not in environ or 'XAUTHORITY' not in environ:
        log.warning('Wine will likely fail to run since DISPLAY or XAUTHORITY are not in the '
                    'environment.')
    esync = environ.get('WINEESYNC', '')
    env = {
        'DISPLAY': environ.get('DISPLAY', ''),
        'PATH': environ['PATH'],
        'WINEPREFIX': str(target),
        'XAUTHORITY': environ.get('XAUTHORITY', '')
    } | ({
        'WINEARCH': environ.get('WINEARCH', arch)
    } if arch else {}) | ({
        'WINEESYNC': esync
    } if esync else {})
    if dpi != DEFAULT_DPI:
        cmd: tuple[str, ...] = ('wine', 'reg', 'add', r'HKCU\Control Panel\Desktop', '/t',
                                'REG_DWORD', '/v', 'LogPixels', '/d', str(dpi), '/f')
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, env=env, check=True, capture_output=True, text=True)
    if dxva_vaapi:
        cmd = ('wine', 'reg', 'add', r'HKCU\Software\Wine\DXVA2', '/t', 'REG_SZ', '/v', 'backend',
               '/d', 'va', '/f')
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, env=env, check=True, capture_output=True, text=True)
    if eax:
        cmd = ('wine', 'reg', 'add', r'HKCU\Software\Wine\DirectSound', '/t', 'REG_SZ', '/v',
               'EAXEnabled', '/d', 'Y', '/f')
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, env=env, check=True, capture_output=True, text=True)
    if gtk:
        cmd = ('wine', 'reg', 'add', r'HKCU\Software\Wine', '/t', 'REG_SZ', '/v', 'ThemeEngine',
               '/d', 'GTK', '/f')
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, env=env, check=True, capture_output=True, text=True)
    if winrt_dark:
        for k in ('AppsUseLightTheme', 'SystemUsesLightTheme'):
            cmd = ('wine', 'reg', 'add',
                   r'HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', '/t',
                   'REG_DWORD', '/v', k, '/d', '0', '/f')
            log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
            sp.run(cmd, env=env, check=True, capture_output=True, text=True)
    if no_xdg:
        cmd = ('wine', 'reg', 'add', r'HKCU\Software\Wine\DllOverrides', '/t', 'REG_SZ', '/v',
               'winemenubuilder.exe', '/f')
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, env=env, check=True, capture_output=True, text=True)
    if dxvk_nvapi:
        tricks += ['dxvk']
    if not (winetricks := which('winetricks')):
        raise FileNotFoundError('winetricks')
    try:
        tricks += [WINETRICKS_VERSION_MAPPING[windows_version]]
        if sandbox:
            tricks += ['isolate_home', 'sandbox']
        if vd != 'off':
            tricks += [f'vd={vd}']
        cmd = (winetricks, '--force', '--country=US', '--unattended', f'prefix={prefix_name}',
               *sorted(set(tricks)))
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, check=True, capture_output=True, text=True)
    except sp.CalledProcessError as e:
        log.warning('Winetricks exit code was %d but it may have succeeded.', e.returncode)
        log.debug('STDERR: %s', e.stderr)
        log.debug('STDOUT: %s', e.stdout)
    if dxvk_nvapi:
        cmd = ('setup_vkd3d_proton.sh', 'install')
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, env=env, check=True, capture_output=True, text=True)
        version = '0.8.1'
        prefix = f'nvidia-libs-{version}'
        r = requests.get(
            f'https://github.com/SveSop/nvidia-libs/releases/download/v{version}/{prefix}.tar.xz',
            timeout=15)
        r.raise_for_status()
        with xz.open(BytesIO(r.content)) as xz_file, tarfile.TarFile(fileobj=xz_file) as tar:
            for item in ('nvcuda', 'nvcuvid', 'nvencodeapi', 'nvapi'):
                cmd = ('wine', 'reg', 'add', r'HKCU\Software\Wine\DllOverrides', '/v', item, '/d',
                       'native', '/f')
                log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
                sp.run(cmd, env=env, check=True, capture_output=True, text=True)
                member = tar.getmember(f'{prefix}/x32/{item}.dll')
                member.name = f'{item}.dll'
                tar.extract(member, target / 'drive_c' / 'windows' / 'syswow64')
            if not _32bit:
                for item in ('nvcuda', 'nvoptix', 'nvcuvid', 'nvencodeapi64', 'nvapi64',
                             'nvofapi64'):
                    cmd = ('wine64', 'reg', 'add', r'HKCU\Software\Wine\DllOverrides', '/v', item,
                           '/d', 'native', '/f')
                    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
                    sp.run(cmd, env=env, check=True, capture_output=True, text=True)
                    member = tar.getmember(f'{prefix}/x64/{item}.dll')
                    member.name = f'{item}.dll'
                    tar.extract(member, target / 'drive_c' / 'windows' / 'system32')
        for prefix in ('', '_'):
            copyfile(f'/lib64/nvidia/wine/{prefix}nvngx.dll',
                     target / 'drive_c' / 'windows' / 'system32' / f'{prefix}nvngx.dll')
        cmd = ('wine64', 'reg', 'add', r'HKLM\Software\NVIDIA Corporation\Global\NGXCore', '/t',
               'REG_SZ', '/v', 'FullPath', '/d', r'C:\Windows\system32', '/f')
        log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
        sp.run(cmd, env=env, check=True, capture_output=True, text=True)

    return target


def secure_move_path(client: SSHClient,
                     filename: StrPath,
                     remote_target: str,
                     *,
                     dry_run: bool = False,
                     preserve_stats: bool = False,
                     write_into: bool = False) -> None:
    log.debug('Source: "%s", remote target: "%s"', filename, remote_target)

    def mkdir_ignore_existing(sftp: SFTPClient, td: str, times: tuple[float, float]) -> None:
        if not write_into:
            log.debug('MKDIR "%s"', td)
            if not dry_run:
                sftp.mkdir(td)
                if preserve_stats:
                    sftp.utime(td, times)
            return
        try:
            sftp.stat(td)
        except FileNotFoundError:
            log.debug('MKDIR "%s"', td)
            if not dry_run:
                sftp.mkdir(td)
                if preserve_stats:
                    sftp.utime(td, times)

    path = Path(filename)
    _, stdout, __ = client.exec_command('echo "${HOME}"')
    remote_target = remote_target.replace('~', stdout.read().decode().strip())
    with client.open_sftp() as sftp:
        if path.is_file():
            if not dry_run:
                sftp.put(filename, remote_target)
                if preserve_stats:
                    local_s = Path(filename).stat()
                    sftp.utime(remote_target, (local_s.st_atime, local_s.st_mtime))
            log.debug('Deleting local file "%s".', path)
            if not dry_run:
                path.unlink()
        else:
            dirs_made = set()
            pf = Path(filename)
            pf_stat = pf.stat()
            bn_filename = pf.name
            dn_prefix = str(pf).replace(bn_filename, '')
            mkdir_ignore_existing(sftp, remote_target, (pf_stat.st_atime, pf_stat.st_mtime))
            for root, dirs, files in os.walk(filename, followlinks=True):
                p_root = Path(root)
                remote_target_dir = f'{remote_target}/{bn_filename}'
                if p_root.is_dir() and remote_target_dir not in dirs_made:
                    p_root_stat = p_root.stat()
                    mkdir_ignore_existing(sftp, remote_target_dir,
                                          (p_root_stat.st_atime, p_root_stat.st_mtime))
                    dirs_made.add(remote_target_dir)
                for name in sorted(dirs):
                    p_root_stat = (p_root / name).stat()
                    dp = str(p_root / name).replace(dn_prefix, '')
                    remote_target_dir = f'{remote_target}/{dp}'
                    if remote_target_dir not in dirs_made:
                        mkdir_ignore_existing(sftp, remote_target_dir,
                                              (p_root_stat.st_atime, p_root_stat.st_mtime))
                        dirs_made.add(remote_target_dir)
                for name in sorted(files):
                    src = p_root / name
                    dp = str(p_root / name).replace(dn_prefix, '')
                    log.debug('PUT "%s" "%s/%s"', src, remote_target, dp)
                    if not dry_run:
                        sftp.put(src, f'{remote_target}/{dp}')
                        if preserve_stats:
                            local_s = Path(src).stat()
                            sftp.utime(f'{remote_target}/{dp}',
                                       (local_s.st_atime, local_s.st_mtime))
                    log.debug('Deleting local file "%s".', src)
                    if not dry_run:
                        src.unlink()
            deleted_dirs: set[StrPath] = set()
            for root, dirs, _ in os.walk(filename, followlinks=True, topdown=False):
                p_root = Path(root)
                for name in dirs:
                    prn = p_root / name
                    if prn not in deleted_dirs:
                        log.debug('Deleting local subdirectory "%s".', prn)
                        if not dry_run:
                            prn.rmdir()
                        deleted_dirs.add(prn)
                if p_root not in deleted_dirs:
                    log.debug('Deleting local root directory "%s".', p_root)
                    if not dry_run:
                        p_root.rmdir()
                    deleted_dirs.add(p_root)


@overload
def kill_processes_by_name(name: str) -> None:
    pass


@overload
def kill_processes_by_name(name: str,
                           wait_timeout: float,
                           signal: int = SIGTERM,
                           *,
                           force: bool = False) -> list[int]:
    pass


def kill_processes_by_name(name: str,
                           wait_timeout: float | None = None,
                           signal: int = SIGTERM,
                           *,
                           force: bool = False) -> list[int] | None:
    """
    Terminate processes by name.

    Alternative to using `psutil <https://pypi.org/project/psutil/>`_.
    
    Parameters
    ----------
    name : str
        Process name (base name) or image name (Windows).
    wait_timeout : float | None
        If set and processes remain after ending processes, wait this amount of time in seconds.
    signal : int
        Signal to use. Only applies to non-Windows.
    force : bool
        If ``wait_timeout`` is set and ``True``, forcefully end the processes after the wait time.

    Returns
    -------
    list[int] | None
        PIDs of processes that may still be running, or ``None`` if ``wait_timeout`` is not
        specified.
    """
    name = f'{name}{Path(name).suffix or ".exe"}' if IS_WINDOWS else name
    pids: list[int] = []
    if IS_WINDOWS:
        sp.run(('taskkill.exe', '/im', name), check=False, capture_output=True)
    else:
        sp.run(('killall', f'-{signal}', name), check=False, capture_output=True)
    if wait_timeout:
        lines = sp.run(
            ('tasklist.exe', '/fo', 'csv', '/fi', f'IMAGENAME eq {name}') if IS_WINDOWS else
            ('ps', 'ax'),
            check=True,
            capture_output=True,
            text=True).stdout.splitlines()
        if pids := [int(x[1]) for x in list(csv.reader(lines))[1:]] if IS_WINDOWS else [
                int(y[0]) for y in (x.split() for x in lines) if Path(y[0]).name == name
        ]:
            time.sleep(wait_timeout)
            if force:
                sp.run(('taskkill.exe', *(t for sl in (('/pid', str(pid)) for pid in pids)
                                          for t in sl), '/f') if IS_WINDOWS else
                       ('kill', '-9', *(str(x) for x in pids)),
                       check=False,
                       capture_output=True)
    return pids if wait_timeout else None
