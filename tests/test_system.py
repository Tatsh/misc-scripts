from typing import Any, Never
from unittest import mock
import os

from pytest_mock import MockerFixture
import pytest

from tatsh_misc_utils.system import (
    find_bluetooth_device_info_by_name,
    get_inhibitor,
    inhibit_notifications,
    kill_gamescope,
    patch_macos_bundle_info_plist,
    slug_rename,
    uninhibit_notifications,
    wait_for_disc,
)
from tatsh_misc_utils.typing import CDStatus

INHIBIT_SUCCESS_CODE = 1234


def make_fake_system_bus() -> tuple[Any, mock.Mock]:
    manager = mock.Mock()

    class FakeSystemBus:
        def get(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {'org.freedesktop.login1.Manager': manager}

    return FakeSystemBus, manager


def make_fake_session_bus() -> tuple[Any, mock.Mock]:
    notifications = mock.Mock()

    class FakeSessionBus:
        def get(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return notifications

    return FakeSessionBus, notifications


def test_get_inhibitor_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fsb, manager = make_fake_system_bus()
    manager.Inhibit.return_value = INHIBIT_SUCCESS_CODE
    monkeypatch.setattr('pydbus.SystemBus', fsb)
    result = get_inhibitor('sleep', 'test_user', 'testing', 'block')
    assert result == INHIBIT_SUCCESS_CODE
    manager.Inhibit.assert_called_once_with('sleep', 'test_user', 'testing', 'block')


def test_inhibit_notifications_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fsb, mock_notifications = make_fake_session_bus()
    monkeypatch.setattr('pydbus.SessionBus', fsb)
    mock_notifications.Inhibited = False
    mock_notifications.Inhibit.return_value = 1234
    result = inhibit_notifications('test_app', 'testing')
    assert result is True
    mock_notifications.Inhibit.assert_called_once_with('test_app', 'testing', {})


def test_inhibit_notifications_already_inhibited(monkeypatch: pytest.MonkeyPatch) -> None:
    fsb, mock_notifications = make_fake_session_bus()
    monkeypatch.setattr('pydbus.SessionBus', fsb)
    mock_notifications.Inhibited = True
    result = inhibit_notifications('test_app', 'testing')
    assert result is False


def test_uninhibit_notifications_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fsb, mock_notifications = make_fake_session_bus()
    monkeypatch.setattr('pydbus.SessionBus', fsb)
    mock_notifications.Inhibited = True
    mock_notifications.UnInhibit.return_value = None
    monkeypatch.setattr('tatsh_misc_utils.system._key', 1234)
    uninhibit_notifications()
    mock_notifications.UnInhibit.assert_called_once_with(1234)


def test_uninhibit_notifications_not_inhibited(monkeypatch: pytest.MonkeyPatch) -> None:
    fsb, mock_notifications = make_fake_session_bus()
    monkeypatch.setattr('pydbus.SessionBus', fsb)
    mock_notifications.Inhibited = False
    uninhibit_notifications()
    mock_notifications.UnInhibit.assert_not_called()


def test_wait_for_disc_success(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_ioctl(*args: Any) -> CDStatus:
        return CDStatus.DISC_OK

    monkeypatch.setattr('fcntl.ioctl', mock_ioctl)
    mock_context_os_open = mocker.patch('tatsh_misc_utils.system.context_os_open')
    result = wait_for_disc()
    assert result is True
    mock_context_os_open.assert_called_once_with('dev/sr0', os.O_RDONLY | os.O_NONBLOCK)


def test_wait_for_disc_keyboard_interrupt(mocker: MockerFixture,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_ioctl(*args: Any) -> Never:
        raise KeyboardInterrupt

    monkeypatch.setattr('fcntl.ioctl', mock_ioctl)
    mock_context_os_open = mocker.patch('tatsh_misc_utils.system.context_os_open')
    assert wait_for_disc() is False
    mock_context_os_open.assert_called_once_with('dev/sr0', os.O_RDONLY | os.O_NONBLOCK)


def make_fake_bluez_system_bus() -> tuple[Any, mock.Mock]:
    manager = mock.Mock()

    class FakeSystemBus:
        def get(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {'org.freedesktop.DBus.ObjectManager': manager}

    return FakeSystemBus, manager


def test_find_bluetooth_device_info_by_name_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fsb, mock_bluez = make_fake_bluez_system_bus()
    mock_bluez.GetManagedObjects.return_value = {
        '/org/bluez/hci0/dev_00_11_22_33_44_55': {
            'org.bluez.Device1': {
                'Name': 'TestDevice'
            }
        }
    }
    monkeypatch.setattr('pydbus.SystemBus', fsb)
    result = find_bluetooth_device_info_by_name('TestDevice')
    assert result == ('/org/bluez/hci0/dev_00_11_22_33_44_55', {'Name': 'TestDevice'})
    mock_bluez.GetManagedObjects.assert_called_once()


def test_find_bluetooth_device_info_by_name_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    fsb, mock_bluez = make_fake_bluez_system_bus()
    mock_bluez.GetManagedObjects.return_value = {}
    monkeypatch.setattr('pydbus.SystemBus', fsb)
    with pytest.raises(KeyError):
        find_bluetooth_device_info_by_name('TestDevice')


def test_find_bluetooth_device_info_by_name_not_linux(mocker: MockerFixture) -> None:
    mocker.patch('tatsh_misc_utils.system.IS_LINUX', False)  # noqa: FBT003
    with pytest.raises(NotImplementedError):
        find_bluetooth_device_info_by_name('TestDevice')


def test_slug_rename_success(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('tatsh_misc_utils.system.Path')
    mock_slugify = mocker.patch('tatsh_misc_utils.system.slugify')
    mock_path.return_value.resolve.return_value = mock_path
    mock_path.parent = mock_path
    mock_slugify.return_value = 'slugified_name'
    result = slug_rename('test_path')
    assert result == mock_path.rename.return_value
    mock_path.return_value.resolve.assert_called_once_with(strict=True)
    mock_slugify.assert_called_once_with(mock_path.name, no_lower=False)
    mock_path.rename.assert_called_once_with(mock_path / 'slugified_name')


def test_patch_macos_bundle_info_plist_success(mocker: MockerFixture) -> None:
    mock_path = mocker.patch('tatsh_misc_utils.system.Path')
    mock_plistlib = mocker.patch('tatsh_misc_utils.system.plistlib')
    mock_info_plist = mock_path.return_value.resolve.return_value.__truediv__.return_value.__truediv__.return_value  # noqa: E501
    mock_info_plist.open.return_value.__enter__.return_value = mock.Mock()
    patch_macos_bundle_info_plist('test_bundle', key='value')
    mock_info_plist.open.assert_any_call('rb')
    mock_info_plist.open.assert_any_call('wb')
    mock_plistlib.load.assert_called_once()
    mock_plistlib.dump.assert_called_once()
    mock_info_plist.touch.assert_called_once()


def test_kill_gamescope_success(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_proc_gs = mock.Mock()
    mock_proc_gs.info = {'name': 'gamescope'}
    mock_proc_gsr = mock.Mock()
    mock_proc_gsr.info = {'name': 'gamescopereaper'}
    mock_proc_not_gs = mock.Mock()
    mock_proc_not_gs.info = {'name': 'not_gamescope'}

    def mock_process_iter(*args: Any) -> Any:
        nonlocal mock_proc_gs, mock_proc_gsr, mock_proc_not_gs
        return [mock_proc_gs, mock_proc_gsr, mock_proc_not_gs]

    monkeypatch.setattr('psutil.process_iter', mock_process_iter)
    kill_gamescope()
    mock_proc_gs.kill.assert_called_once()
    mock_proc_gsr.kill.assert_called_once()
    mock_proc_not_gs.kill.assert_not_called()
