from typing import Any, Literal, overload

class Notifications:
    Inhibited: bool

    def UnInhibit(self, key: int) -> int | None:
        ...

    def Inhibit(self, unk1: str, unk2: str, unk3: Any) -> int | None:
        ...

class SessionBus:
    @overload
    def get(self, domain: Literal['org.freedesktop.Notifications'],
            path: Literal['/org/freedesktop/Notifications']) -> Notifications:
        ...

    @overload
    def get(self, domain: str, path: str) -> Any:
        ...
