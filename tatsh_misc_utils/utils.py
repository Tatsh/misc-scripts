from binascii import crc32
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, datetime
from html import escape
from itertools import chain
from math import trunc
from os import getxattr, scandir
from pathlib import Path
from time import sleep
from typing import cast
from zipfile import ZipFile
import contextlib
import fcntl
import os
import platform
import plistlib
import re

from .typing import CDStatus, FileDescriptorOrPath, StrPath

__all__ = ('IS_LINUX', 'add_cdda_times', 'chunks', 'context_os_open', 'hexstr2bytes',
           'hexstr2bytes_generator', 'wait_for_disc', 'where_from')

CDROM_DRIVE_STATUS = 0x5326
IS_LINUX = platform.uname().system == 'Linux'
KEY_ORIGIN_URL = 'user.xdg.origin.url'
KEY_WHERE_FROMS = 'com.apple.metadata:kMDItemWhereFroms'
ZERO_TO_59 = '|'.join(f'{x:02d}' for x in range(60))
ZERO_TO_74 = '|'.join(f'{x:02d}' for x in range(75))
TIMES_RE = re.compile(f'^({ZERO_TO_59}):({ZERO_TO_59}):({ZERO_TO_74})$')
MAX_FRAMES = 75
MAX_MINUTES = 99
MAX_SECONDS = 60


def chunks(seq: str, n: int) -> Iterator[str]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def hexstr2bytes_generator(s: str) -> Iterator[int]:
    for hex_num in chunks(s, 2):
        yield int(hex_num, 16)


def hexstr2bytes(s: str) -> bytes:
    return bytes(hexstr2bytes_generator(s))


@contextlib.contextmanager
def context_os_open(path: str,
                    flags: int,
                    mode: int = 511,
                    *,
                    dir_fd: int | None = None) -> Iterator[int]:
    f = os.open(path, flags, mode, dir_fd=dir_fd)
    yield f
    os.close(f)


def wait_for_disc(drive_path: str = 'dev/sr0', *, sleep_time: float = 1.0) -> bool | None:
    """For Linux only."""
    with context_os_open(drive_path, os.O_RDONLY | os.O_NONBLOCK) as f:
        s = -1
        try:
            while s != CDStatus.DISC_OK:
                s = fcntl.ioctl(f, CDROM_DRIVE_STATUS, 0)
                if s == CDStatus.NO_INFO:
                    return None
                if s != CDStatus.DISC_OK:
                    sleep(sleep_time)
        except KeyboardInterrupt:
            pass
    return s != CDStatus.DISC_OK


def where_from(file: FileDescriptorOrPath, *, webpage: bool = False) -> str | None:
    index = 1 if webpage else 0
    attr_value = getxattr(file, KEY_ORIGIN_URL if IS_LINUX else KEY_WHERE_FROMS).decode()
    if not IS_LINUX:
        attr_value = cast(Sequence[str], plistlib.loads(hexstr2bytes(attr_value)))[index]
    return attr_value


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


def unpack_0day(path: StrPath, *, remove_diz: bool = True) -> None:
    """Unpack RAR files from 0day zip file sets.
    
    Parameters
    ----------
    path : str
        Path where zip files are located.
    remove_diz : bool
        Remove any files matching `*.diz` glob (not case-sensitive). Defaults to ``True``.
    """
    path = Path(path)
    with contextlib.chdir(path):
        for zip_file in path.glob('*.zip'):
            with ZipFile(zip_file) as z:
                z.extractall()
            zip_file.unlink()
        if remove_diz:
            for diz in path.glob('*.diz', case_sensitive=False):
                diz.unlink()
        rars = list(path.glob('*.rar'))
        with Path(re.sub(r'(?:\.part\d+)?\.r(?:[0-9][0-9]|ar)$', '.sfv',
                         rars[0].name.lower())).open('w+', encoding='utf-8') as f:
            f.write(f'; {datetime.now(tz=UTC).astimezone()}\n')
            for rar in sorted(
                    path.glob('*.part*.rar' if any(
                        re.search(r'\.part[0-9]{,3}\.rar$', str(r), re.IGNORECASE)
                        for r in rars) else '*.[rstuvwxyz][0-9a][0-9r]',
                              case_sensitive=False)):
                f.write(f'{rar.name} {crc32(rar.read_bytes()):08X}\n')


def generate_html_dir_tree(start_dir: StrPath,
                           *,
                           follow_symlinks: bool = False,
                           depth: int = 2) -> str:
    """Generate a HTML directory listing."""
    def recurse_cwd(path: Path, _cur_depth: int = 0) -> Iterator[str]:
        for entry in sorted(sorted(scandir(path), key=lambda x: x.name),
                            key=lambda x: not x.is_dir(follow_symlinks=follow_symlinks)):
            if (entry.is_dir(follow_symlinks=follow_symlinks) and _cur_depth < depth):
                yield ('<li class="dir mui--text-dark mui--text-body2"><details><summary>'
                       f'<code>{escape(entry.name)}/</code></summary><ul>')
                yield from recurse_cwd(Path(entry), _cur_depth=_cur_depth + 1)
                yield '</ul></details></li>'
            else:
                isd = entry.is_dir(follow_symlinks=follow_symlinks)
                class_ = 'file' if not isd else 'dir'
                slash = '' if not isd else '/'
                yield (
                    f'<li class="{class_} mui--text-dark mui--text-body1"><a class="mui--text-dark" '
                    f'href="./{entry.path}"><code>{escape(entry.name)}{slash}</code></a></li>')

    start_dir = Path(start_dir).resolve(strict=True)
    with contextlib.chdir(start_dir):
        title = start_dir.name
        files = ''.join(chain.from_iterable(recurse_cwd(start_dir)))
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contents of {title}/</title>
<link rel="stylesheet" href="https://cdn.muicss.com/mui-0.10.3/css/mui.min.css"
crossorigin="anonymous">
<style>
ul {{
    list-style: none;
    padding-inline-start: 1em;
}}
.dir {{
    cursor: pointer;
}}
.mui-appbar {{
    margin-bottom: 2em;
}}
</style>
</head>
<body>
<header class="mui-appbar mui--z1">
<div class="mui-container-fluid">
<h1 class="mui--text-title">Contents of {title}</h1>
</div>
</header>
<div class="mui-container-fluid">
<ul>{files}</ul>
</div>
</body>
</html>"""
