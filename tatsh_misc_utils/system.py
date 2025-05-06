from __future__ import annotations

from pathlib import Path
from shlex import quote
from time import sleep
from typing import TYPE_CHECKING, Any, cast
import configparser
import json
import logging
import os
import plistlib
import re
import subprocess as sp
import sys

from binaryornot.helpers import is_binary_string

from .io import context_os_open
from .string import slugify
from .typing import CDStatus, StrPath

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydbus.bus import OrgBluezDevice1Dict

__all__ = ('CHROME_DEFAULT_CONFIG_PATH', 'CHROME_DEFAULT_LOCAL_STATE_PATH', 'IS_LINUX',
           'find_bluetooth_device_info_by_name', 'inhibit_notifications', 'slug_rename',
           'uninhibit_notifications', 'wait_for_disc')

CDROM_DRIVE_STATUS = 0x5326
IS_LINUX = sys.platform == 'linux'
IS_WINDOWS = sys.platform == 'win32' or sys.platform == 'cygwin'
CHROME_DEFAULT_CONFIG_PATH = Path('~/.config/google-chrome').expanduser()
CHROME_DEFAULT_LOCAL_STATE_PATH = str(CHROME_DEFAULT_CONFIG_PATH / 'Local State')
log = logging.getLogger(__name__)


def wait_for_disc(drive_path: StrPath = 'dev/sr0', *, sleep_time: float = 1.0) -> bool:
    """For Linux only."""
    import fcntl  # noqa: PLC0415
    with context_os_open(drive_path, os.O_RDONLY | os.O_NONBLOCK) as f:
        s = -1
        try:
            while (s := fcntl.ioctl(f, CDROM_DRIVE_STATUS)) != CDStatus.DISC_OK:
                sleep(sleep_time)
        except KeyboardInterrupt:
            pass
    return s == CDStatus.DISC_OK


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
    except (ImportError, ModuleNotFoundError):  # pragma: no cover
        log.exception('Cannot import pydbus.', stack_info=False)
        return False
    notifications = SessionBus().get('org.freedesktop.Notifications')
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
    notifications = SessionBus().get('org.freedesktop.Notifications')
    if not notifications:
        raise ConnectionError
    if not notifications.Inhibited:
        return
    if _key is not None:
        notifications.UnInhibit(_key)
        _key = None


def get_inhibitor(what: str, who: str, why: str, mode: str) -> int:
    try:
        from pydbus import SystemBus  # noqa: PLC0415
    except (ImportError, ModuleNotFoundError):  # pragma: no cover
        log.exception('Cannot import pydbus.', stack_info=False)
        return -1
    login1 = SystemBus().get('org.freedesktop.login1', '/org/freedesktop/login1')
    return cast('int', login1['org.freedesktop.login1.Manager'].Inhibit(what, who, why, mode))


def find_bluetooth_device_info_by_name(name: str) -> tuple[str, OrgBluezDevice1Dict]:
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


def pan_connect(device_mac: str, hci: str = 'hci0') -> None:
    """
    Connect a Bluetooth PAN device for internet access.
    
    For Linux with NetworkManager only.

    This function must be called and then waited by an event loop.

    Translation of the following command:

    ... code-block:: bash
       dbus-send --system --type=method_call --dest=org.bluez \
           /org/bluez/hci0/dev_{MAC with : replaced by _} \
           org.bluez.Network1.Connect \
           string:nap
    """
    if not IS_LINUX:
        raise NotImplementedError
    from pydbus import SystemBus  # noqa: PLC0415
    device_mac = f"dev_{device_mac.upper().replace(':', '_')}"
    device = SystemBus().get('org.bluez', f'/org/bluez/{hci}/{device_mac}')
    device.Connect('nap')


def pan_disconnect(device_mac: str, hci: str = 'hci0') -> None:
    """
    Disconnect a Bluetooth PAN device.
    
    For Linux with NetworkManager only.

    This function must be called and then waited by an event loop.

    Translation of the following command:

    ... code-block:: bash
       dbus-send --system --type=method_call --dest=org.bluez \
           /org/bluez/hci0/dev_{MAC with : replaced by _} \
           org.bluez.Network1.Disconnect
    """
    if not IS_LINUX:
        raise NotImplementedError
    from pydbus import SystemBus  # noqa: PLC0415
    device_mac = f"dev_{device_mac.upper().replace(':', '_')}"
    device = SystemBus().get('org.bluez', f'/org/bluez/{hci}/{device_mac}')
    device.Disconnect()


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


def kill_wine() -> None:
    """If a process is named with ``.exe``, it is assumed to be a Wine process."""
    import psutil  # noqa: PLC0415
    for proc in (x for x in psutil.process_iter(('pid', 'name', 'username'))
                 if x.info['name'] in {'wineserver', 'wine-preloader', 'wine64-preloader'} or (
                     x.info['name'].lower().endswith('.exe'))):
        proc.kill()


class MultipleKeySlots(Exception):
    """Exception raised when a device has more than one keyslot."""
    def __init__(self, dev: str) -> None:
        super().__init__(f'Device {dev} has more than one keyslot. This is not supported.')


def reset_tpm_enrollment(uuid: str, *, dry_run: bool = True) -> None:
    """
    Reset the systemd-cryptsetup TPM enrolment for a device.
    
    Requires root privileges.
    """
    dev = f'/dev/disk/by-uuid/{uuid}'
    cmd = ('cryptsetup', 'luksDump', '--dump-json-metadata', dev)
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    info = json.loads(sp.run(cmd, check=True, capture_output=True).stdout)
    systemd_tokens = [(k, x) for k, x in info['tokens'].items() if x['type'] == 'systemd-tpm2']
    if not systemd_tokens:
        log.debug('No tokens found for device %s.', dev)
        return
    systemd_token_id = systemd_tokens[0][0]
    n_keyslots = len(info['tokens'][systemd_token_id]['keyslots'])
    if n_keyslots > 1:
        raise MultipleKeySlots(dev)
    slot = info['tokens'][systemd_token_id]['keyslots'][0]
    luks_kill_slot_cmd = ('cryptsetup', 'luksKillSlot', dev, slot)
    luks_kill_slot_cmd_quoted = ' '.join(quote(x) for x in luks_kill_slot_cmd)
    luks_token_remove_cmd = ('cryptsetup', 'token', 'remove', f'--token-id={systemd_token_id}', dev)
    luks_token_remove_cmd_quoted = ' '.join(quote(x) for x in luks_token_remove_cmd)
    cryptenroll_cmd = ('systemd-cryptenroll', '--tpm2-device=auto', dev)
    cryptenroll_cmd_quoted = ' '.join(quote(x) for x in cryptenroll_cmd)
    if dry_run:
        log.info('Would run: %s', luks_kill_slot_cmd_quoted)
        log.info('Would run: %s', luks_token_remove_cmd_quoted)
        log.info('Would run: %s', cryptenroll_cmd_quoted)
    else:
        log.debug('Running: %s', luks_kill_slot_cmd_quoted)
        sp.run(luks_kill_slot_cmd, check=True)
        log.debug('Running: %s', luks_token_remove_cmd_quoted)
        sp.run(luks_token_remove_cmd, check=True)
        log.debug('Running: %s', cryptenroll_cmd_quoted)
        sp.run(cryptenroll_cmd, check=True)
        log.info('Reset TPM enrolment for %s.', uuid)


IGNORED_GROUPS = {
    'KFileDialog Settings', 'FileDialogSize', 'Recent Files[$e]', 'Recent URLs[$e]', 'Recent Files',
    '$Version'
}
DEFAULT_FILE = Path.home() / '.config' / 'kdeglobals'
POSITION_RE = (
    r'(^(Height|Width|Window-Maximized) [0-9]+)|'
    r'((e?DP-[0-9]+|HDMI-[0-9]+(-[0-9]+)?|VNC-[0-9]+)$)|'
    r'((e?DP-[0-9]+|HDMI-[0-9]+(-[0-9]+)?|VNC-[0-9]+) (Height|Width|(X|Y)Position|Window-Maximized))|'  # noqa: E501
    r'([0-9]+x[0-9]+ screen: (Height|Width|(X|Y)Position)$)|'
    r'([0-9] screens: (Height|Width|(X|Y)Position)$)')
STATE_RE = r'^AAAA/'


def get_kwriteconfig_commands(file: StrPath = DEFAULT_FILE) -> Iterator[str]:
    home = str(Path.home())
    config = configparser.ConfigParser(delimiters=('=',), interpolation=None)
    config.optionxform = str  # type: ignore[assignment]
    file = Path(file).resolve(strict=True)
    displayed_file = re.sub(rf'^{home}/', '~/', str(file))
    try:
        config.read(file)
    except (UnicodeDecodeError, configparser.MissingSectionHeaderError, configparser.ParsingError):
        log.warning('Cannot parse "%s".', file)
        return
    for section in config.sections():
        if '][' in section:
            log.debug('Skipping unsupported section "%s".', section)
            continue
        if section in IGNORED_GROUPS:
            log.debug('Ignoring section "%s".', section)
            continue
        for key, value in config[section].items():
            if is_binary_string(value.encode()):
                log.debug('Ignoring binary value in key %s.', key)
                continue
            is_int = re.match(r'^-?[0-9]+$', value)
            if re.search(POSITION_RE, key):
                log.debug('Skipping metrics key "%s".', key)
                continue
            if key == 'State' and re.search(STATE_RE, value):
                log.debug('Skipping state key.')
                continue
            if key.endswith('[$e]'):
                log.debug('Skipping special key "%s".', key)
                continue
            type_ = None
            try:
                is_file = '/' in value and Path(value).exists()
            except OSError:
                is_file = False
            if is_file:
                type_ = 'path'
            elif re.match(r'^(?:1|true|false|on|yes)$', value):
                type_ = 'bool'
            elif is_int:
                type_ = 'int'
            cmd: tuple[str, ...] = ('kwriteconfig6',)
            if file != DEFAULT_FILE:
                cmd += ('--file', displayed_file)
            if type_:
                cmd += ('--type', quote(type_))
            cmd += ('--group', quote(section), '--key', quote(key), quote(value))
            yield ' '.join(cmd)
