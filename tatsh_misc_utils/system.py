from time import sleep
import fcntl
import os
import platform

from .io import context_os_open
from .typing import CDStatus

CDROM_DRIVE_STATUS = 0x5326
IS_LINUX = platform.uname().system == 'Linux'

__all__ = ('IS_LINUX', 'wait_for_disc')


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
