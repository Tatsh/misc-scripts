from io import BufferedReader
from typing import Sequence

class GPG:
    encoding: str

    def __init__(self,
                 gnupghome: str | None = ...,
                 verbose: bool | None = ...,
                 use_agent: bool | None = ...) -> None:
        ...

    def encrypt_file(self, data: BufferedReader | str, recipients: Sequence[str],
                     output: str) -> None:
        ...
