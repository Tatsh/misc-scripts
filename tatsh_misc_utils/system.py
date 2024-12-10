from __future__ import annotations

from pathlib import Path
from time import sleep
from typing import Any
import logging
import os
import plistlib
import sys

from .io import context_os_open
from .string import slugify
from .typing import CDStatus, StrPath

__all__ = ('CHROME_DEFAULT_LOCAL_STATE_PATH', 'IS_LINUX', 'find_bluetooth_device_info_by_name',
           'inhibit_notifications', 'slug_rename', 'uninhibit_notifications', 'wait_for_disc')

CDROM_DRIVE_STATUS = 0x5326
IS_LINUX = sys.platform == 'linux'
IS_WINDOWS = sys.platform == 'win32' or sys.platform == 'cygwin'
CHROME_DEFAULT_LOCAL_STATE_PATH: str | None = str(
    Path('~/.config/google-chrome/Local State').expanduser())
log = logging.getLogger(__name__)


def wait_for_disc(drive_path: str = 'dev/sr0', *, sleep_time: float = 1.0) -> bool | None:
    """For Linux only."""
    import fcntl  # noqa: PLC0415
    with context_os_open(drive_path, os.O_RDONLY | os.O_NONBLOCK) as f:
        s = -1
        try:
            while s != CDStatus.DISC_OK:
                s = fcntl.ioctl(f, CDROM_DRIVE_STATUS, 0)
                if s != CDStatus.DISC_OK:
                    sleep(sleep_time)
        except KeyboardInterrupt:
            pass
    return s != CDStatus.DISC_OK


_key: int | None = None


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
    try:
        from pydbus import SessionBus  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError):
        log.exception('Cannot import pydbus.', stack_info=False)
        return False
    notifications = SessionBus().get('org.freedesktop.Notifications',
                                     '/org/freedesktop/Notifications')
    if notifications.Inhibited:
        return False
    log.debug('Disabling notifications.')
    _key = notifications.Inhibit(name, reason, {})
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
    try:
        from pydbus import SessionBus  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError):
        log.exception('Cannot import pydbus.', stack_info=False)
        return
    notifications = SessionBus().get('org.freedesktop.Notifications',
                                     '/org/freedesktop/Notifications')
    if not notifications:
        raise ConnectionError
    if not notifications.Inhibited:
        return
    if _key is not None:
        notifications.UnInhibit(_key)
        _key = None


def find_bluetooth_device_info_by_name(name: str) -> tuple[str, dict[str, Any]]:
    """
    Get Bluetooth device information from D-Bus (bluez) by name.
    
    Note that not all devices present a name.

    Parameters
    ----------
    name : str
        Name of the device. Case sensitive.

    Returns
    -------
    tuple[str, dict[str, Any]]]
        Returns the D-Bus object path and a dictionary representing the ``org.bluez.Device1``
        properties.

    Raises
    ------
    NotImplementedError
        If not on Linux.
    KeyError
        If no device is found.
    """
    if not IS_LINUX:
        raise NotImplementedError
    from pydbus import SystemBus  # noqa: PLC0415
    bluez = SystemBus().get('org.bluez', '/')
    for k, v in bluez['org.freedesktop.DBus.ObjectManager'].GetManagedObjects().items():
        if ('org.bluez.Device1' in v and 'Name' in v['org.bluez.Device1']
                and v['org.bluez.Device1']['Name'] == name):
            return k, v['org.bluez.Device1']
    raise KeyError(name)


def slug_rename(path: StrPath, *, no_lower: bool = False) -> StrPath:
    path = Path(path).resolve(strict=True)
    parent = path.parent
    return path.rename(parent / slugify(path.name, no_lower=no_lower))


def patch_macos_bundle_info_plist(bundle: StrPath, **data: Any) -> None:
    """
    Patch a macOS/iOS/etc bundle's ``Info.plist`` file.

    Example
    -------
    .. code-block :: python

        # Force Retina support
        patch_macos_bundle_info_plist('App.app', {'NSHighResolutionCapable': True})

    Parameters
    ----------
    bundle : StrPath
        Path to the bundle.
    data : dict[str, Any]
        Data to merge in.
    """
    info_plist = Path(bundle).resolve(strict=True) / 'Contents' / 'Info.plist'
    with info_plist.open('rb') as f:
        file_data: dict[str, Any] = plistlib.load(f)
    with info_plist.open('wb') as f:
        plistlib.dump(file_data | data, f, sort_keys=False)
    info_plist.touch()


def kill_gamescope() -> None:
    import psutil  # noqa: PLC0415
    for proc in (x for x in psutil.process_iter(('pid', 'name', 'username'))
                 if x.info['name'] in {'gamescope', 'gamescopereaper'}):
        proc.kill()
