from binascii import crc32
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile
import contextlib
import io
import logging
import os
import re
import shutil
import subprocess as sp

from .typing import StrPath

log = logging.getLogger(__name__)


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


def extract_rar_from_zip(zip_file: ZipFile) -> Iterator[str]:
    for x in (x for x in zip_file.namelist() if re.search(r'\.r(?:ar|\d{2})$', x)):
        zip_file.extract(x)
        yield x


def unpack_ebook(path: StrPath) -> None:
    def unrar_x(rar: StrPath) -> None:
        sp.run(('unrar', 'x', '-y', str(rar)), capture_output=True, check=True)

    if not (path := Path(path)).is_dir():
        raise NotADirectoryError
    with contextlib.chdir(path):
        zip_listing = frozenset(ZipFile(x) for x in os.listdir('.') if x.endswith('.zip'))
        if len(zip_listing) == 0:
            raise FileExistsError
        extracted = [Path(x) for y in (extract_rar_from_zip(z) for z in zip_listing) for x in y]
        rar = next((x for x in extracted if x.name.endswith('.rar')), None)
        if not rar:
            raise ValueError(0)
        # Only need the .rar
        unrar_x(rar)
        epub_list = [Path(x) for x in os.listdir('.') if x.lower().endswith('.epub')]
        pdf_list = [Path(x) for x in os.listdir('.') if x.lower().endswith('.pdf')]
        if not pdf_list and not epub_list:
            raise ValueError(0)
        if pdf_list:
            if len(pdf_list) > 1:
                log.debug('More than one PDF extracted. Not sure what to do.')
                raise ValueError(len(pdf_list))
            with pdf_list[0].open('rb') as f:
                if (sig := f.read(4)) != b'%PDF':
                    log.warning('PDF file extracted but is not a PDF.')
                    raise ValueError(sig)
            pdf_name = pdf_list[0].resolve(strict=True).parent.name
            ext = 'pdf'
        else:
            if len(epub_list) > 1:
                log.warning('More than one ePub extracted. Not sure what to do.')
                raise ValueError(len(epub_list))
            pdf_name = epub_list[0].resolve(strict=True).parent.name
            ext = 'epub'
            pdf_list = epub_list
        pdf_list[0].rename(f'../{pdf_name}.{ext}')
        for zip_file in zip_listing:
            zip_file.close()
        for x in extracted:
            x.unlink()


GOG_FILESIZE_RE = re.compile(r'filesizes="(\d+?)"')
GOG_OFFSET_RE = re.compile(r'offset=`head -n (\d+?) "\$0"')


def extract_gog(filename: str, output_dir: StrPath) -> None:
    """Extract a Linux gog.com archive."""
    output_dir = Path(output_dir)
    input_path = Path(filename).resolve(strict=True)
    with input_path.open('rb') as game_bin:
        output_dir.mkdir(parents=True)
        # Read the first 10kb so we can determine the script line number
        beginning = game_bin.read(10240).decode('utf-8', errors='ignore')
        offset_match = GOG_OFFSET_RE.search(beginning)
        if not offset_match:
            raise ValueError
        script_lines = int(offset_match.group(1))
        # Read the number of lines to determine the script size
        game_bin.seek(0, io.SEEK_SET)
        for _ in range(script_lines):
            game_bin.readline()
        script_size = game_bin.tell()
        log.debug('Makeself script size: %d', script_size)
        # Read the script
        game_bin.seek(0, io.SEEK_SET)
        script_bin = game_bin.read(script_size)
        with (output_dir / 'unpacker.sh').open('wb') as script_f:
            script_f.write(script_bin)
        script = script_bin.decode()
        # Filesize is for the MojoSetup archive, not the actual game data
        filesize_match = GOG_FILESIZE_RE.search(script)
        if not filesize_match:
            raise ValueError
        filesize = int(filesize_match.group(1))
        log.debug('MojoSetup archive size: %d', filesize)
        # Extract the setup archive
        game_bin.seek(script_size, io.SEEK_SET)
        with (output_dir / 'mojosetup.tar.gz').open('wb') as setup_f:
            setup_f.write(game_bin.read(filesize))
        # Extract the game data archive
        dataoffset = script_size + filesize
        game_bin.seek(dataoffset, io.SEEK_SET)
        with (output_dir / 'data.zip').open('wb') as datafile:
            shutil.copyfileobj(game_bin, datafile)
