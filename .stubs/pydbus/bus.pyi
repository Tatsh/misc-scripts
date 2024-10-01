from typing import Any, Literal, overload

from gi.repository.Gio import DBusConnection


class Notifications:
    Inhibited: bool

    def UnInhibit(self, key: int) -> int | None:  # noqa: N802
        ...

    def Inhibit(self, unk1: str, unk2: str, unk3: Any) -> int | None:  # noqa: N802
        ...


class Bus:
    con: DBusConnection

    @overload
    def get(self, domain: Literal['org.freedesktop.Notifications'],
            path: Literal['/org/freedesktop/Notifications']) -> Notifications:
        ...

    @overload
    def get(self, domain: str, path: str) -> Any:
        ...


def SessionBus() -> Bus:  # noqa: N802
    ...


def SystemBus() -> Bus:  # noqa: N802
    ...
