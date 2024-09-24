from binascii import crc32
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile
import contextlib
import os
import re

from .typing import StrPath


@contextlib.contextmanager
def context_os_open(path: str,
                    flags: int,
                    mode: int = 511,
                    *,
                    dir_fd: int | None = None) -> Iterator[int]:
    """Context-managed file descriptor opener."""
    f = os.open(path, flags, mode, dir_fd=dir_fd)
    yield f
    os.close(f)


def unpack_0day(path: StrPath, *, remove_diz: bool = True) -> None:
    """Unpack RAR files from 0day zip file sets.
    
    Parameters
    ----------
    path : str
        Path where zip files are located.
    remove_diz : bool
        Remove any files matching `*.diz` glob (not case-sensitive). Defaults to ``True``.
    """
    path = Path(path)
    with contextlib.chdir(path):
        for zip_file in path.glob('*.zip'):
            with ZipFile(zip_file) as z:
                z.extractall()
            zip_file.unlink()
        if remove_diz:
            for diz in path.glob('*.diz', case_sensitive=False):
                diz.unlink()
        rars = list(path.glob('*.rar'))
        with Path(re.sub(r'(?:\.part\d+)?\.r(?:[0-9][0-9]|ar)$', '.sfv',
                         rars[0].name.lower())).open('w+', encoding='utf-8') as f:
            f.write(f'; {datetime.now(tz=UTC).astimezone()}\n')
            for rar in sorted(
                    path.glob('*.part*.rar' if any(
                        re.search(r'\.part[0-9]{,3}\.rar$', str(r), re.IGNORECASE)
                        for r in rars) else '*.[rstuvwxyz][0-9a][0-9r]',
                              case_sensitive=False)):
                f.write(f'{rar.name} {crc32(rar.read_bytes()):08X}\n')
