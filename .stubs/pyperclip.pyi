from collections.abc import Callable
from typing import Literal

def copy(text: str) -> None:
    ...

def paste() -> str:
    ...

ClipboardType = Literal[  # noqa: PYI026
    'klipper', 'no', 'pbcopy', 'pyobjc', 'qt', 'windows', 'wl-clipboard', 'xclip', 'xsel']

def set_clipboard(clipboard: ClipboardType) -> None:
    ...

def determine_clipboard() -> tuple[Callable[[str], None], Callable[[], str]]:
    ...
