from typing import Any, Literal, TypedDict, overload

from gi.repository.Gio import DBusConnection

OrgBluezDict = TypedDict(
    'OrgBluezDict', {
        'org.bluez.AgentManager1': dict[Any, Any],
        'org.bluez.ProfileManager1': dict[Any, Any],
        'org.freedesktop.DBus.Introspectable': dict[Any, Any]
    })
OrgBluesHci0Dict = TypedDict('OrgBluesHci0Dict', {'org.bluez.Adapter1': dict[str, Any]})

DBusOrgFreedesktopDBusObjectManagerManagedObjectsDict = TypedDict(
    'DBusOrgFreedesktopDBusObjectManagerManagedObjectsDict',  # noqa: PYI053
    {
        '/org/bluez': OrgBluezDict,
        '/org/bluez/hci0': OrgBluesHci0Dict
    })


class DBusOrgFreedesktopDBusObjectManager:
    x: int
    y: int

    @staticmethod
    def GetManagedObjects() -> dict[str, Any]:  # noqa: N802
        ...


class Bluez:
    def __getitem__(
            self, key: Literal['org.freedesktop.DBus.ObjectManager']
    ) -> DBusOrgFreedesktopDBusObjectManager:
        ...


class Notifications:
    Inhibited: bool

    def UnInhibit(self, key: int) -> int | None:  # noqa: N802
        ...

    def Inhibit(self, name: str, reason: str, unk1: Any) -> int | None:  # noqa: N802
        ...


class Bus:
    con: DBusConnection

    @overload
    def get(self, domain: Literal['org.freedesktop.Notifications'],
            path: Literal['/org/freedesktop/Notifications']) -> Notifications:
        ...

    @overload
    def get(self, domain: Literal['org.bluez'], path: Literal['/']) -> Bluez:
        ...

    @overload
    def get(self, domain: str, path: str) -> Any:
        ...


def SessionBus() -> Bus:  # noqa: N802
    ...


def SystemBus() -> Bus:  # noqa: N802
    ...
