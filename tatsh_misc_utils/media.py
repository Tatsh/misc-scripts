"""Media-related utility functions."""
from collections.abc import Sequence
from datetime import datetime
from os import utime
from pathlib import Path
from shutil import copyfile
from typing import Any, ClassVar, NamedTuple
import contextlib
import ctypes
import getpass
import json
import logging
import operator
import os
import re
import socket
import subprocess as sp
import tempfile

import keyring
import requests

from .io import context_os_open
from .system import IS_LINUX
from .typing import StrPath, assert_not_none

__all__ = ('CDDBQueryResult', 'add_info_json_to_media_file', 'cddb_query', 'ffprobe',
           'get_cd_disc_id', 'get_info_json', 'is_audio_input_format_supported',
           'supported_audio_input_formats')

log = logging.getLogger(__name__)


def supported_audio_input_formats(
    input_device: str,
    *,
    formats: Sequence[str] = ('f32be', 'f32le', 'f64be', 'f64le', 's8', 's16be', 's16le', 's24be',
                              's24le', 's32be', 's32le', 'u8', 'u16be', 'u16le', 'u24be', 'u24le',
                              'u32be', 'u32le'),
    rates: Sequence[int] = (8000, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200,
                            96000, 128000, 176400, 192000, 352800, 384000)
) -> tuple[tuple[str, int], ...]:
    """
    Get supported input formats and sample rates by invoking ``ffmpeg``.

    For possible formats, invoke ``ffmpeg``: ``ffmpeg -formats | grep PCM | cut '-d ' -f3``.
    
    Parameters
    ----------
    device : str
        Device name. Platform specific. Examples: `'hw:Audio'`, 'hw:NVidia'`.

    formats : Sequence[str]
        Formats to check.

    rates : Sequence[int]
        Rates in Hz to check. The default set is taken from possible frequencies for DTS format.

    Returns
    -------
    tuple[tuple[str, int], ...]
        A tuple of ``(format, rate)`` tuples.
    """
    ret = []
    for format_ in formats:
        for rate in rates:
            log.debug('Checking pcm_%s @ %d.', format_, rate)
            p = sp.run(('ffmpeg', '-hide_banner', '-loglevel', 'info', '-f', 'alsa', '-acodec',
                        f'pcm_{format_}', '-ar', str(rate), '-i', input_device),
                       text=True,
                       capture_output=True,
                       check=False)
            all_output = p.stdout.strip() + p.stderr.strip()
            if 'Device or resource busy' in all_output or 'No such device' in all_output:
                raise OSError
            log.debug('Output: %s', all_output)
            if 'cannot set sample format 0x' in all_output or f'{rate} Hz' not in all_output:
                continue
            ret.append((format_, rate))
    return tuple(ret)


def is_audio_input_format_supported(
        input_device: str,
        format: str,  # noqa: A002
        rate: int) -> bool:
    return bool(supported_audio_input_formats(input_device, formats=(format,), rates=(rate,)))


def add_info_json_to_media_file(path: StrPath,
                                info_json: StrPath | None = None,
                                *,
                                debug: bool = False) -> None:
    """
    Add yt-dlp ``info.json`` file to media file at ``path``.

    On successful completion, the ``info.json`` file will be deleted.

    This function will exist until yt-dlp embeds ``info.json`` in all formats it supports where
    possible.

    This function requires the following:

    - For FLAC, MP3, and Opus: `ffmpeg <https://ffmpeg.org/>`_.
    - For MP4: `gpac <https://gpac.io/>`_.

    Parameters
    ----------
    path : StrPath
        Path to FLAC, MP3, MP4, or Opus media file.

    info_json : StrPath | None
        Path to ``info.json`` file. If not passed, ``path`` with suffix changed to ``info.json``
        is used.
    """
    path = Path(path)
    json_path = Path(info_json) if info_json else path.with_suffix('.info.json')

    def set_date() -> None:
        with json_path.open() as fp:
            data = json.load(fp)
        try:
            upload_date = data['upload_date'].strip()
        except KeyError:
            log.debug('Upload date key not found.')
            return
        if not upload_date:
            log.debug('No upload date to set.')
            return
        log.debug('Setting date to %s.', upload_date)
        seconds = datetime.strptime(upload_date, '%Y%m%d').timestamp()  # noqa: DTZ007
        utime(path, times=(seconds, seconds))

    def mkvpropedit_add_json() -> None:
        if any(
                re.match((r"^Attachment ID \d+: type 'application/json', size \d+ bytes, "
                          "file name 'info.json'"), line)
                for line in sp.run(('mkvmerge', '--identify', str(path)),
                                   capture_output=True,
                                   check=True,
                                   text=True).stdout.splitlines()):
            log.warning('Attachment named info.json already exists. Not modifying file.')
            return
        log.debug('Attaching info.json to MKV.')
        sp.run(('mkvpropedit', str(path), '--attachment-name', 'info.json', '--add-attachment',
                str(json_path)),
               check=True,
               capture_output=not debug)
        set_date()

    def flac_mp3_add_json() -> None:
        log.debug('Attaching info.json.')
        with (tempfile.NamedTemporaryFile(suffix=path.suffix, delete=False, dir=path.parent) as tf,
              tempfile.NamedTemporaryFile(suffix='.ffmetadata',
                                          encoding='utf-8',
                                          dir=path.parent,
                                          mode='w+') as ffm):
            sp.run(('ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-i', f'file:{path}',
                    '-f', 'ffmetadata', f'{ffm.name}'),
                   check=True,
                   capture_output=True)
            lines = Path(ffm.name).read_text(encoding='utf-8').splitlines(keepends=True)
            escaped = re.sub(r'([=;#\\\n])', r'\\\1', json_path.read_text())
            is_mp3 = path.suffix == '.mp3'
            key = r'TXXX=info_json\=' if is_mp3 else 'info_json='
            lines.insert(1, f'{key}{escaped}\n')
            with (tempfile.NamedTemporaryFile(suffix='.ffmetadata',
                                              encoding='utf-8',
                                              dir=path.parent,
                                              delete=False,
                                              mode='w+') as nfw):
                nfw.writelines(lines)
            sp.run(('ffmpeg', '-y', '-i', f'file:{path}', '-i', f'file:{nfw.name}', '-map_metadata',
                    '1', '-c', 'copy', *(('-write_id3v1', '1') if is_mp3 else
                                         ()), f'file:{tf.name}'),
                   capture_output=not debug,
                   check=True)
            Path(tf.name).rename(path)
            Path(nfw.name).unlink()
        set_date()

    def mp4box_add_json() -> None:
        with contextlib.suppress(sp.CalledProcessError):
            sp.run(('MP4Box', '-rem-item', '1', str(path)), check=False)
        sp.run(('MP4Box', '-set-meta', 'mp21', str(path)), capture_output=not debug, check=True)
        info_json_path = Path('info.json')
        copyfile(json_path, info_json_path)
        log.debug('Attaching info.json to MP4.')
        sp.run(('MP4Box', '-add-item',
                (f'{info_json_path}:replace:name=youtube-dl metadata:mime=application/json:'
                 'encoding=utf8'), str(path)),
               check=False,
               capture_output=not debug)
        info_json_path.unlink()
        set_date()

    if not json_path.exists():
        log.warning('JSON path not found.')
        return
    match path.suffix.lower()[1:]:
        case 'flac' | 'mp3' | 'opus':
            flac_mp3_add_json()
        case 'm4a' | 'm4b' | 'm4p' | 'm4r' | 'm4v' | 'mp4':
            mp4box_add_json()
        case 'mkv':
            mkvpropedit_add_json()
        case _:
            return
    json_path.unlink()


def ffprobe(path: StrPath) -> Any:
    """Run ``ffprobe`` and decode its JSON output."""
    return json.loads(
        sp.run(('ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
                str(path)),
               text=True,
               capture_output=True,
               check=True).stdout.strip())


def get_info_json(path: StrPath, *, raw: bool = False) -> Any:
    """
    Get ``info.json`` content in ``path``.

    Parameters
    ----------
    path : StrPath
        Path to FLAC, MP3, MP4, or Opus media file.

    raw : bool
        If raw, do not decode.

    Returns
    -------
    Any
        The JSON data decoded. Currently not typed.
    """
    path = Path(path)
    match path.suffix.lower()[1:]:
        case 'flac':
            out = ffprobe(path)['format']['tags']['info_json']
        case 'm4a' | 'm4b' | 'm4p' | 'm4r' | 'm4v' | 'mp4':
            out = sp.run(('MP4Box', '-dump-item', '1:path=/dev/stdout', str(path)),
                         check=True,
                         capture_output=True,
                         text=True).stdout.strip()
        case 'mkv':
            out = sp.run(('mkvextract', str(path), 'attachments', '1:/dev/stdout'),
                         check=True,
                         capture_output=True,
                         text=True).stdout.strip().splitlines()[1]
        case 'mp3':
            out = ffprobe(path)['format']['tags']['TXXX'].replace('info_json=', '', 1)
        case 'opus':
            out = ffprobe(path)['streams'][0]['tags']['info_json']
        case _:
            raise NotImplementedError
    return out if raw else json.loads(out)


def create_static_text_video(audio_file: StrPath,
                             text: str,
                             font: str = 'Roboto',
                             *,
                             debug: bool = False,
                             nvenc: bool = False,
                             videotoolbox: bool = False) -> None:
    """
    Create a video file consisting of static text in the centre with the audio file passed in.

    Requires ImageMagick and ffmpeg.

    Parameters
    ----------
    audio_file : StrPath
        Path to audio file.

    text : str
        Text to show.

    nvenc : bool
        Use NVENC.

    virtualbox : bool
        Use VideoToolbox.
    """
    if nvenc and videotoolbox:
        msg = 'nvenc and videotoolbox parameters are exclusive. Only one can be set to True.'
        raise ValueError(msg)
    audio_file = Path(audio_file)
    out = f'{audio_file.parent}/{audio_file.stem}-audio.mkv'
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir=Path.cwd()) as tf:
        try:
            sp.run(('magick', '-font', font, '-size', '1920x1080', 'xc:black', '-fill', 'white',
                    '-pointsize', '50', '-draw', f"gravity Center text 0,0 '{text}'", tf.name),
                   check=True,
                   capture_output=not debug)
        except sp.CalledProcessError:
            Path(tf.name).unlink()
            raise
    args_start: tuple[str,
                      ...] = ('ffmpeg', '-loglevel', 'warning', '-hide_banner', '-y', '-loop', '1',
                              '-i', tf.name, '-i', str(audio_file), '-shortest', '-acodec', 'copy')
    if nvenc:
        args_start += ('-vcodec', 'h264_nvenc', '-profile:v', 'high', '-level', '1', '-preset',
                       'llhq', '-coder:v', 'cabac', '-b:v', '1M')
    elif videotoolbox:
        args_start += ('-vcodec', 'hevc_videotoolbox', '-profile:v', 'main', '-level', '1', '-b:v',
                       '0.5M')
    else:
        args_start += ('-vcodec', 'libx265', '-crf', '20', '-level', '1', '-profile:v', 'main')
    log.debug('Output: %s', out)
    sp.run((*args_start, '-pix_fmt', 'yuv420p', '-b:v', '1M', '-maxrate:v', '1M', out),
           check=True,
           capture_output=not debug)
    Path(tf.name).unlink()


CDROMREADTOCHDR = 0x5305
CDROMREADTOCENTRY = 0x5306
CDROM_LBA = 1
CD_MSF_OFFSET = 150
CD_FRAMES = 75
CDROM_LEADOUT = 0xAA


class CDROMMSF0(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [('minute', ctypes.c_ubyte),
                                                 ('second', ctypes.c_ubyte),
                                                 ('frame', ctypes.c_ubyte)]


class CDROMAddress(ctypes.Union):
    _fields_: ClassVar[list[tuple[str, Any]]] = [('msf', CDROMMSF0), ('lba', ctypes.c_int)]


class CDROMTOCEntry(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any] | tuple[str, Any, int]]] = [
        ('cdte_track', ctypes.c_ubyte), ('cdte_adr', ctypes.c_ubyte, 4),
        ('cdte_ctrl', ctypes.c_ubyte, 4), ('cdte_format', ctypes.c_ubyte),
        ('cdte_addr', CDROMAddress), ('cdte_datamode', ctypes.c_ubyte)
    ]


class CDROMTOCHeader(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [('cdth_trk0', ctypes.c_ubyte),
                                                 ('cdth_trk1', ctypes.c_ubyte)]


def get_cd_disc_id(drive: str) -> str:
    if not IS_LINUX:
        raise OSError

    def cddb_sum(n: int) -> int:
        # a number like 2344 becomes 2+3+4+4 (13)
        ret = 0
        while n > 0:
            ret += n % 10
            n //= 10
        return ret

    with context_os_open(drive, os.O_RDONLY | os.O_NONBLOCK) as fd:
        libc = ctypes.CDLL('libc.so.6', use_errno=True)
        toc_header = CDROMTOCHeader()
        if libc.ioctl(fd, CDROMREADTOCHDR, ctypes.byref(toc_header)) < 0:
            raise OSError(ctypes.get_errno())
        last: int = toc_header.cdth_trk1
        toc_entries = []
        for i in range(last):
            buf = CDROMTOCEntry()
            buf.cdte_track = i + 1
            buf.cdte_format = CDROM_LBA
            toc_entries.append(buf)
            if libc.ioctl(fd, CDROMREADTOCENTRY, ctypes.byref(buf)):
                raise OSError(ctypes.get_errno())
        buf = CDROMTOCEntry()
        buf.cdte_track = CDROM_LEADOUT
        buf.cdte_format = CDROM_LBA
        toc_entries.append(buf)
        if libc.ioctl(fd, CDROMREADTOCENTRY, ctypes.byref(buf)) < 0:
            raise OSError(ctypes.get_errno())
    checksum = 0
    for entry in toc_entries[:-1]:
        checksum += cddb_sum((entry.cdte_addr.lba + CD_MSF_OFFSET) // CD_FRAMES)
    total_time: int = ((toc_entries[-1].cdte_addr.lba + CD_MSF_OFFSET) // CD_FRAMES) - (
        (toc_entries[0].cdte_addr.lba + CD_MSF_OFFSET) // CD_FRAMES)
    # This expression inside f'{}' causes a Yapf parsing error
    entries = ' '.join(f'{x.cdte_addr.lba + CD_MSF_OFFSET}' for x in toc_entries[:-1])
    return (f'{(checksum % 0xff) << 24 | total_time << 8 | last:08x} {last} '
            f'{entries} '
            f'{(toc_entries[-1].cdte_addr.lba + CD_MSF_OFFSET) // CD_FRAMES}')


class CDDBQueryResult(NamedTuple):
    artist: str
    album: str
    year: int
    genre: str
    tracks: tuple[str, ...]


def cddb_query(disc_id: str,
               *,
               app: str = 'tatsh_misc_utils cddb_query',
               host: str | None = None,
               timeout: float = 5,
               username: str | None = None,
               version: str = '0.0.1') -> CDDBQueryResult:
    """
    Run a query against a CDDB host.
    
    Defaults to host in Keyring under the ``gnudb`` key and current user name.

    It is advised to ``except`` typical
    `Requests exceptions https://requests.readthedocs.io/en/latest/`_ when calling this.

    Parameters
    ----------
    app: str
        App name.
    host: str
        Hostname to query.
    timeout: float
        HTTP timeout.
    username: str
        Username for keyring and for the ``hello`` parameter to the CDDB server.
    version : str
        Application version.

    Returns
    -------
    CDDBQueryResult
        Tuple with artist, album, year, genre, and tracks.
    
    Raises
    ------
    ValueError
        If the server response code is not ``'200'`` or ``'210'`` (these are CDDB codes **not**
        HTTP status codes.)
    """
    username = username or getpass.getuser()
    if not username:
        raise ValueError(username)
    host = host or keyring.get_password('gnudb', username)
    if not host:
        raise ValueError(host)
    this_host = socket.gethostname()
    hello = {'hello': f'{username} {this_host} {app} {version}', 'proto': '6'}
    server = f'http://{host}/~cddb/cddb.cgi'
    params = {'cmd': f'cddb query {disc_id}', **hello}
    r = requests.get(server, params=params, timeout=timeout, headers={'user-agent': hello['hello']})
    r.raise_for_status()
    lines = r.text.splitlines()
    first_line = lines[0].split(' ', 3)
    disc_genre = disc_year = None
    if len(lines) == 1 and first_line[0] == '200':
        _, category, __, artist_title = first_line
    elif first_line[0] == '210':
        # Take first result
        category, _, artist_title = lines[1].split(' ', 2)
    else:
        raise ValueError(first_line[0])
    artist, disc_title = artist_title.split(' / ', 1)
    r = requests.get(server,
                     params={
                         'cmd': f'cddb read {category} {disc_id}',
                         **hello
                     },
                     timeout=timeout)
    r.raise_for_status()
    tracks = {}
    disc_genre = None
    disc_year = None
    for line in (x.strip() for x in r.text.splitlines()[1:]
                 if x.strip() and x[0] not in {'.', '#'}):
        field_name, value = line.split('=', 1)
        match field_name:
            case 'DTITLE':
                artist, disc_title = value.split(' / ', 1)
            case 'DYEAR':
                disc_year = int(value)
            case 'DGENRE':
                disc_genre = value
            case key:
                if key.startswith('TTITLE'):
                    tracks[assert_not_none(re.match(r'^TTITLE([^=]+).*', key)).group(1)] = value
    assert disc_genre is not None
    assert disc_year is not None
    return CDDBQueryResult(artist, disc_title, disc_year, disc_genre,
                           tuple(x[1] for x in sorted(tracks.items(), key=operator.itemgetter(0))))
