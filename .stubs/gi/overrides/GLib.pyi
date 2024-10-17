from typing import Any, Literal, overload

class GError(Exception):
    ...

class Variant:
    @overload
    def __getitem__(self, index: Literal[0]) -> str:
        ...

    @overload
    def __getitem__(self, index: Literal[1]) -> dict[str, Any]:
        ...

    @overload
    def __getitem__(self, index: int) -> str | dict[str, Any]:
        ...
