from collections.abc import Callable
from typing import Any

from gi.overrides.GLib import Variant

class DBusConnection:
    def signal_subscribe(self, unk1: Any, iface: str, signal: str, unk2: Any, unk3: Any, unk4: int,
                         handler: Callable[[Any, Any, str, Any, Any, Variant], None]) -> None:
        ...
