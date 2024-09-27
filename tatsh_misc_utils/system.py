from time import sleep
import fcntl
import logging
import os
import re
import subprocess as sp
import sys

import pexpect

from .io import context_os_open
from .typing import CDStatus

try:
    from pydbus import SessionBus
except ImportError:
    SessionBus = None

__all__ = ('IS_LINUX', 'inhibit_notifications', 'uninhibit_notifications', 'wait_for_disc')

CDROM_DRIVE_STATUS = 0x5326
IS_LINUX = sys.platform == 'linux'
IS_WINDOWS = sys.platform == 'win32' or sys.platform == 'cygwin'
log = logging.getLogger(__name__)


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


_key: int | None = None
_NOTIFICATIONS_BUS = (SessionBus().get('org.freedesktop.Notifications',
                                       '/org/freedesktop/Notifications') if SessionBus else None)


def inhibit_notifications(name: str = __name__, reason: str = 'No reason specified.') -> bool:
    """
    Disable notifications.

    This function is meant to be called from a separate thread from the working task thread during
    initialisation.

    Parameters
    ----------
    name : str
        Name of application.
    reason : str
        Reason for inhibition.

    Returns
    -------
    bool
        ``True`` if inhibited, ``False`` otherwise.

    Raises
    ------
    ConnectionError
        If D-Bus connection is not available (which can be caused by not having pydbus installed).
    """
    global _key  # noqa: PLW0603
    if not _NOTIFICATIONS_BUS:
        raise ConnectionError
    if _NOTIFICATIONS_BUS.Inhibited:
        return False
    log.debug('Disabling notifications.')
    _key = _NOTIFICATIONS_BUS.Inhibit(name, reason, {})
    return True


def uninhibit_notifications() -> None:
    """
    Enable notifications.

    This function is meant to be called from a separate thread from the working task thread during
    clean-up.

    This function is not required to be called if the application will exit as the state will be
    restored on clean-up of the D-Bus connection.

    Raises
    ------
    ConnectionError
        If D-Bus connection is not available (which can be caused by not having pydbus installed).
    """
    global _key  # noqa: PLW0603
    if not _NOTIFICATIONS_BUS:
        raise ConnectionError
    if not _NOTIFICATIONS_BUS.Inhibited:
        return
    if _key is not None:
        _NOTIFICATIONS_BUS.UnInhibit(_key)
        _key = None


