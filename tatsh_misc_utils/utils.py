"""Uncategorised utilities."""
from collections.abc import Iterable
from math import trunc
from os import environ
from pathlib import Path
from shutil import rmtree, which
from typing import Literal
import logging
import re
import subprocess as sp

from .typing import StrPath

__all__ = ('WineWindowsVersion', 'add_cdda_times', 'create_wine_prefix')

ZERO_TO_59 = '|'.join(f'{x:02d}' for x in range(60))
ZERO_TO_74 = '|'.join(f'{x:02d}' for x in range(75))
TIMES_RE = re.compile(f'^({ZERO_TO_59}):({ZERO_TO_59}):({ZERO_TO_74})$')
MAX_FRAMES = 75
MAX_MINUTES = 99
MAX_SECONDS = 60
log = logging.getLogger(__name__)


def add_cdda_times(times: Iterable[str] | None) -> str | None:
    if not times:
        return None
    total_ms = 0.0
    for time in times:
        if not (res := re.match(TIMES_RE, time)):
            return None
        minutes, seconds, frames = [float(x) for x in res.groups()]
        total_ms += (minutes *
                     (MAX_SECONDS - 1) * 1000) + (seconds * 1000) + (frames * 1000) / MAX_FRAMES
    minutes = total_ms / (MAX_SECONDS * 1000)
    remainder_ms = total_ms % (MAX_SECONDS * 1000)
    seconds = remainder_ms / 1000
    remainder_ms %= 1000
    frames = (remainder_ms * 1000 * MAX_FRAMES) / 1e6
    if minutes > MAX_MINUTES or seconds > (MAX_SECONDS - 1) or frames > MAX_FRAMES:
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


def create_wine_prefix(prefix_name: str,
                       *,
                       windows_version: WineWindowsVersion = 'xp',
                       vd: str = 'off',
                       debug: bool = False,
                       no_xdg: bool = False,
                       _32bit: bool = False,
                       sandbox: bool = False,
                       prefix_root: StrPath | None = None) -> StrPath:
    """
    Create a Wine prefix with custom settings.

    Requires Wine and winetricks.
    """
    prefix_root = Path(prefix_root) if prefix_root else Path.home() / '.local/share/wineprefixes'
    prefix_root.mkdir(parents=True, exist_ok=True)
    target = prefix_root / prefix_name
    if target.exists():
        raise FileExistsError
    arch = 'win32' if _32bit else None
    if 'DISPLAY' not in environ or 'XAUTHORITY' not in environ:
        log.warning('Wine will likely fail to run since DISPLAY or XAUTHORITY are not in the '
                    'environment.')
    env = {
        'WINEPREFIX': str(target),
        'DISPLAY': environ.get('DISPLAY', ''),
        'XAUTHORITY': environ.get('XAUTHORITY', ''),
        **({
            'WINEARCH': environ.get('WINEARCH', arch)
        } if arch else {})
    }
    if no_xdg:
        try:
            sp.run(('wine', 'reg', 'add', r'HKCU\Software\Wine\DllOverrides', '/t', 'REG_SZ', '/v',
                    'winemenubuilder.exe', '/f'),
                   env=env,
                   check=True,
                   capture_output=not debug)
        except (KeyboardInterrupt, sp.CalledProcessError):
            rmtree(target)
            raise
    else:
        sp.run(('wine', 'reg'), check=False, capture_output=not debug)
    if not (winetricks := which('winetricks')):
        raise FileNotFoundError('winetricks')
    try:
        sp.run((winetricks, f'prefix={prefix_name}', WINETRICKS_VERSION_MAPPING[windows_version],
                *(('isolate_home', 'sandbox') if sandbox else
                  ()), *((f'vd={vd}',) if vd != 'off' else ())),
               check=True,
               capture_output=not debug)
    except sp.CalledProcessError as e:
        log.warning('Winetricks exit code was %d but it may have succeeded.', e.returncode)
        log.debug('STDERR: %s', e.stderr)
        log.debug('STDOUT: %s', e.stdout)
    return target
