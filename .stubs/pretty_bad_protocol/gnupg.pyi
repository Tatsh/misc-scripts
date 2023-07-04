from io import BufferedReader
from typing import Any, AnyStr

class GPG:
    def __init__(self,
                 binary: str | None = ...,
                 homedir: str | None = ...,
                 verbose: bool | int | str | None = ...,
                 use_agent: bool | None = ...,
                 keyring: str | None = ...,
                 secring: str | None = ...,
                 options: list[Any] | None = ...) -> None:
        ...

    def list_keys(self, secret: bool = ...) -> Any:
        ...

    def encrypt(self, data: AnyStr | BufferedReader, *recipients: Any, **kwargs: Any) -> bytes:
        ...
