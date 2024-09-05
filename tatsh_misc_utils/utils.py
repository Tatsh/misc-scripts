from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from math import trunc
from os import getxattr
from time import sleep
from typing import cast
import fcntl
import os
import platform
import plistlib
import re

from .typing import CDStatus, FileDescriptorOrPath

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


@contextmanager
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
