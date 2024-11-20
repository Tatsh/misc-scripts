"""Media-related utility functions."""
from __future__ import annotations

from datetime import datetime
from functools import cache
from itertools import chain
from os import utime
from pathlib import Path
from shlex import quote
from shutil import copyfile
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NamedTuple, cast
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

from send2trash import send2trash
import keyring
import requests

from .io import context_os_open
from .system import IS_LINUX
from .typing import ProbeDict, StrPath, assert_not_none

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

__all__ = ('CDDBQueryResult', 'add_info_json_to_media_file', 'archive_dashcam_footage',
           'cddb_query', 'ffprobe', 'get_cd_disc_id', 'get_info_json',
           'is_audio_input_format_supported', 'rip_cdda_to_flac', 'supported_audio_input_formats')

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
    """Check if an audio format is supported by a device."""
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
            sp.run(('MP4Box', '-rem-item', '1', str(path)), capture_output=not debug, check=True)
        sp.run(('MP4Box', '-set-meta', 'mp21', str(path)), capture_output=not debug, check=True)
        info_json_path = Path('info.json')
        copyfile(json_path, info_json_path)
        log.debug('Attaching info.json to MP4.')
        sp.run(('MP4Box', '-add-item',
                (f'{info_json_path}:replace:name=youtube-dl metadata:mime=application/json:'
                 'encoding=utf8'), str(path)),
               check=True,
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


def ffprobe(path: StrPath) -> ProbeDict:
    """Run ``ffprobe`` and decode its JSON output."""
    p = sp.run(('ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
                str(path)),
               check=True,
               capture_output=True,
               text=True)
    return cast(ProbeDict, json.loads(p.stdout.strip()))


def get_info_json(path: StrPath, *, raw: bool = False) -> Any:
    """
    Get ``info.json`` content in ``path``.

    Parameters
    ----------
    path : StrPath
        Path to FLAC, MP3, MP4, or Opus media file.
    raw : bool
        If ``True``, do not decode.

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
    """
    Calculate a CDDB disc ID.

    For Linux only.
    
    Parameters
    ----------
    drive : str
        Drive path.

    Raises
    ------
    NotImplementedError
        If not on Linux.

    Returns
    -------
    str
        String for use with CDDB query.
    """
    if not IS_LINUX:
        raise NotImplementedError

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


@cache
def cddb_query(disc_id: str,
               *,
               accept_first_match: bool = False,
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
    r = requests.get(server,
                     params={
                         'cmd': f'cddb query {disc_id}',
                         **hello
                     },
                     timeout=timeout,
                     headers={'user-agent': hello['hello']})
    r.raise_for_status()
    log.debug('Response:\n%s', r.text.strip())
    lines = r.text.splitlines()
    first_line = lines[0].split(' ', 3)
    disc_genre = disc_year = None
    if len(lines) == 1 and first_line[0] == '200':
        _, category, disc_id, artist_title = first_line
    elif first_line[0] == '210':
        if not accept_first_match:
            log.debug('Results:\n%s', '\n'.join(lines).strip())
            raise ValueError(len(lines[1:-1]))
        category, disc_id, artist_title = lines[1].split(' ', 2)
    else:
        raise ValueError(first_line[0])
    artist, disc_title = artist_title.split(' / ', 1)
    r = requests.get(server,
                     params={
                         'cmd': f'cddb read {category} {disc_id.split(" ")[0]}',
                         **hello
                     },
                     timeout=timeout)
    r.raise_for_status()
    log.debug('Response: %s', r.text)
    tracks = {}
    disc_genre = None
    disc_year = None
    log.debug('Artist: %s', artist)
    log.debug('Album: %s', disc_title)
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


def rip_cdda_to_flac(drive: str,
                     *,
                     accept_first_cddb_match: bool = True,
                     album_artist: str | None = None,
                     album_dir: StrPath | None = None,
                     cddb_host: str | None = None,
                     never_skip: int = 5,
                     output_dir: StrPath | None = None,
                     stderr_callback: Callable[[str], None] | None = None,
                     username: str | None = None) -> None:
    """
    Rip an audio disc to FLAC files.

    Requires ``cdparanoia`` and ``flac`` to be in ``PATH``.
    
    Parameters
    ----------
    album_artist: str | None
        Album artist override.
    accept_first_cddb_match : bool
        Accept the first CDDB match in case of multiple matches.
    cddb_host : str | None
        CDDB host.
    album_dir : StrPath | None
        Album directory to output to. Will be created with parents if it does not exist. Defaults
        to *artist-album-year* format.
    never_skip : int
        Passed to ``cdparanoia``'s ``--never-skip=...`` option.
    output_dir : StrPath | None
        Parent directory for ``album_dir``. Defaults to current directory.
    stderr_callback : Callable[[str], None] | None = None
        If passed, can be used to track progress by interpreting output from ``cdparanoia``. Lines
        will be stripped and only non-empty lines will trigger the callback.
    username: str | None
        Username for CDDB. Defaults to current username.
    """
    result = cddb_query(get_cd_disc_id(drive),
                        app='tatsh_misc_utils rip_cdda',
                        accept_first_match=accept_first_cddb_match,
                        host=cddb_host,
                        username=username)
    log.debug('Result: %s', result)
    output_dir = Path(output_dir or '.')
    album_dir = ((output_dir / album_dir) if album_dir else output_dir /
                 f'{result.artist}-{result.album}-{result.year}')
    album_dir.mkdir(parents=True, exist_ok=True)
    for i, track in enumerate(result.tracks, 1):
        wav = album_dir / f'{i:02d}-{result.artist}-{track}.wav'
        flac = str(wav.with_suffix('.flac'))
        cdparanoia_command = ('cdparanoia', f'--force-cdrom-device={drive}',
                              *(('--quiet', '--stderr-progress') if stderr_callback else
                                ()), f'--never-skip={never_skip:d}', '--abort-on-skip', str(i),
                              str(wav))
        proc = sp.Popen(cdparanoia_command,
                        stderr=sp.PIPE if stderr_callback else None,
                        stdout=sp.PIPE if stderr_callback else None,
                        text=True)
        if stderr_callback:
            assert proc.stderr is not None
            while proc.stderr.readable():
                if line := proc.stderr.readline().strip():
                    stderr_callback(line)
        else:
            log.debug('Waiting for cdparanoia to finish (i = %d, track = "%s").', i, track)
            if (code := proc.wait()) != 0:
                raise sp.CalledProcessError(code, cdparanoia_command)
        sp.run(
            ('flac', '--delete-input-file', '--force', '--replay-gain', '--silent', '--verify',
             f'--output-name={flac}', f'--tag=ALBUM={result.album}',
             f'--tag=ALBUMARTIST={album_artist or result.artist}', f'--tag=ARTIST={result.artist}',
             f'--tag=GENRE={result.genre}', f'--tag=TITLE={track}', f'--tag=TRACKNUMBER={i:02d}',
             f'--tag=YEAR={result.year:04d}', str(wav)),
            check=True)


def group_files(items: Iterable[str],
                clip_length: int = 3,
                match_re: str = r'^(\d+)_.*',
                time_format: str = '%Y%m%d%H%M%S') -> list[list[Path]]:
    items_sorted = sorted(items)
    groups: list[list[Path]] = []
    group: list[Path] = [Path(items_sorted[0]).resolve(strict=True)]
    groups.append(group)
    for item in items_sorted[1:]:
        p = Path(item).resolve(strict=True)
        this_dt = datetime.strptime(  # noqa: DTZ007
            assert_not_none(re.match(match_re,
                                     Path(item).name)).group(1), time_format)
        last_dt = datetime.strptime(  # noqa: DTZ007
            assert_not_none(re.match(match_re,
                                     Path(group[-1]).name)).group(1), time_format)
        diff = (this_dt - last_dt).total_seconds() // 60
        log.debug('Difference for current file %s vs last file %s: %d minutes', p, group[-1], diff)
        if diff > clip_length:
            log.debug('New group started with %s.', p)
            group = [p]
            groups.append(group)
        else:
            group.append(p)
    return groups


def archive_dashcam_footage(front_dir: StrPath,
                            rear_dir: StrPath,
                            output_dir: StrPath,
                            *,
                            allow_group_discrepancy_resolution: bool = True,
                            clip_length: int = 3,
                            hwaccel: str | None = 'auto',
                            level: int | None = 5,
                            overwrite: bool = False,
                            match_re: str = r'^(\d+)_.*',
                            preset: str | None = 'p5',
                            rear_crop: str | None = '1920:1020:0:0',
                            rear_view_scale_divisor: float | None = 2.5,
                            setpts: str | None = '0.25*PTS',
                            temp_dir: StrPath | None = None,
                            tier: str | None = 'high',
                            time_format: str = '%Y%m%d%H%M%S',
                            video_bitrate: str | None = '0k',
                            video_decoder: str | None = 'hevc_cuvid',
                            video_encoder: str = 'hevc_nvenc',
                            video_max_bitrate: str | None = '15M') -> None:
    """
    Batch encode dashcam footage, merging rear and front camera footage.

    This functions's defaults are intended for use with Red Tiger dashcam output and file structure.

    The rear camera view will be placed in the bottom right of the video scaled by dividing the
    width and height by the ``rear_view_scale_divisor`` value specified. It will also be cropped
    using the ``rear_crop`` value unless it is ``None``.

    Files are automatically grouped using the regular expression passed with ``match_re``. This
    RE must contain at least one group and only the first group will be considered. Make dubious use
    of non-capturing groups if necessary. The captured group string is expected to be usable with
    the time format specified with ``time_format`` (see strptime documentation at
    https://docs.python.org/3/library/datetime.html#datetime.datetime.strptime).

    In many cases, the camera leaves behind stray rear camera files (usually no more than one per
    group and always a video without a matching front video file the end). These are automatically
    ignored if possible.

    Original files' whose content is successfully converted are sent to the wastebin.

    Example:

    .. code::python

        archive_dashcam_footage('Movie_F', 'Movie_R', Path.home() / 'output')

    Parameters
    ----------
    front_dir : StrPath
        Directory containing front footage.
    rear_dir : StrPath
        Directory containing rear footage.
    output_dir : StrPath
        Will be created if it does not exist including parents.
    allow_group_discrepancy_resolution : bool
        Attempt to solve grouping discrepancies (count of files) automatically.
    clip_length : int
        Clip length in minutes.
    hwaccel : str | None
        String passed to ffmpeg's ``-hwaccel`` option.
    level : int | None
        Level (HEVC).
    overwrite : bool
        Overwrite existing files.
    match_re : str
        Regular expression used for finding the timestamp in a filename. Must contain at least one
        group and only the first group is considered.
    preset : str | None
        Preset (various codecs).
    rear_crop : str | None
        Crop string for the rear video. See `ffmpeg crop filter`_ for more information.
    rear_view_scale_divisor : float
        Scaling divisor for rear view.
    setpts : str | None
        Change the PTS. See `ffmpeg setpts filter`_ for more information. The default is to increase
        the speed of the video up by 4x.
    temp_dir : StrPath | None
        Temporary directory root.
    tier : str | None
        Tier (HEVC).
    time_format : str
        Time format string. See `strptime() Format Codes`_ for more information.
        for more information.
    video_bitrate : str | None
        Video bitrate string.
    video_decoder : str | None
        Video decoder.
    video_encoder : str
        Video encoder.
    video_max_bitrate : str | None
        Maximum video bitrate.

    Raises
    ------
    FileExistsError
        If an output file exists and ``overwrite`` is not ``True``.
    ValueError
        ``zip()`` is used to group pairs of file groups and the front and rear videos. Strict mode
        is used and as such length counts must always match, unless a workaround is known. If a
        workaround cannot be used, this exception will be raised from ``zip()``.

    .. ffmpeg crop filter: https://ffmpeg.org/ffmpeg-filters.html#crop
    .. ffmpeg setpts filter: https://ffmpeg.org/ffmpeg-filters.html#setpts_002c-asetpts
    .. strptime() Format Codes: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
    """
    front_dir = Path(front_dir)
    rear_dir = Path(rear_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Do not sort the dicts
    input_options: list[str] = list(
        chain(*((k, *((str(v),) if not isinstance(v, bool) and v is not None else ())) for k, v in {
            '-y': overwrite,
            '-hwaccel': hwaccel,
            **({
                '-c:v': video_decoder
            } if hwaccel else {})
        }.items() if v)))
    crop_str = f'crop={rear_crop},' if rear_crop else ''
    setpts_str = f',setpts={setpts}' if setpts else ''
    output_options = list(
        chain(*((k, *((str(v),) if not isinstance(v, bool) and v is not None else ())) for k, v in {
            '-an': True,
            '-filter_complex': (
                f'[0]{crop_str}'
                f'scale=iw/{rear_view_scale_divisor}:ih/{rear_view_scale_divisor} [pip]; '
                f'[1][pip]overlay=main_w-overlay_w:main_h-overlay_h{setpts_str}'),
            '-b:v': video_bitrate,
            '-maxrate:v': video_max_bitrate,
            '-vcodec': video_encoder,
            '-preset': preset,
            '-level': level,
            '-tier': tier,
            '-f': 'matroska'
        }.items() if v)))
    back_groups = group_files(
        (str(rear_dir / x) for x in os.listdir(rear_dir) if not x.startswith('.')), clip_length,
        match_re, time_format)
    front_groups = group_files(
        (str(front_dir / x) for x in os.listdir(front_dir) if not x.startswith('.')), clip_length,
        match_re, time_format)
    back_groups_len = len(back_groups)
    front_groups_len = len(front_groups)
    log.debug('Back group count: %d', back_groups_len)
    log.debug('Front group count: %d', front_groups_len)
    if back_groups_len != front_groups_len:
        if not allow_group_discrepancy_resolution:
            raise ValueError(back_groups_len)
        log.warning('Length of front and back groups do not match. Attempting resolution.')
        back_groups = [x for x in back_groups if len(x) > 1]
        back_groups_len = len(back_groups)
        if back_groups_len != front_groups_len:
            raise ValueError(back_groups_len)
        log.info('Possibly resolved length issue by ignoring single item rear videos.')
    # Call list(zip(...)) so strictness can be checked before looping
    for back_group, front_group in list(zip(back_groups, front_groups, strict=True)):
        with tempfile.NamedTemporaryFile('w',
                                         dir=temp_dir,
                                         encoding='utf-8',
                                         prefix='concat-',
                                         suffix='.txt') as temp_concat:
            fg_len = len(front_group)
            bg_len = len(back_group)
            log.debug('Back group length: %d', bg_len)
            log.debug('Front group length: %d', fg_len)
            for i, item in enumerate(back_group):
                log.debug('Front: %-40s Back: %s', front_group[i].name if i < fg_len else 'NOTHING',
                          item.name)
            if fg_len != bg_len:
                if not allow_group_discrepancy_resolution:
                    raise ValueError(bg_len)
                log.warning('List lengths of front and back videos do not match.')
                if bg_len - fg_len == 1:
                    last = back_group.pop()
                    log.debug('Sent to wastebin: %s', last)
                    send2trash(last)
                    log.info('Possibly resolved length issue by ignoring last rear video in set.')
                elif fg_len - bg_len == 1:
                    last = front_group.pop()
                    log.debug('Sent to wastebin: %s', last)
                    send2trash(last)
                    log.info('Possibly resolved length issue by ignoring last front video in set.')
                else:
                    log.error('Cannot resolve automatically.')
            to_be_merged: list[Path] = []
            send_to_waste: list[Path] = []
            for i, (back_file, front_file) in enumerate(
                    list(zip(back_group, front_group, strict=True))):
                log.debug('Back file: %s, front file: %s', back_file, front_file)
                assert back_file != front_file
                cmd = ('ffmpeg', '-hide_banner', *input_options, '-i', str(back_file), '-i',
                       str(front_file), *output_options, '-')
                send_to_waste += [front_file, back_file]
                log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
                with tempfile.NamedTemporaryFile(delete=False,
                                                 dir=temp_dir,
                                                 prefix=f'{i:04d}-',
                                                 suffix='.mkv') as tf:
                    try:
                        sp.run(cmd, stdout=tf, check=True, stderr=sp.PIPE)
                    except sp.CalledProcessError as e:
                        log.exception('STDERR: %s', e.stderr.decode())
                        for path in to_be_merged:
                            path.unlink()
                        raise
                    tf_fixed = Path(tf.name).resolve(strict=True)
                    to_be_merged.append(tf_fixed)
                    temp_concat.write(f"file '{tf_fixed}'\n")
            temp_concat.flush()
            full_output_path = output_dir / front_group[0].with_suffix('.mkv').name
            if not overwrite:
                suffix = 1
                while full_output_path.exists():
                    offset = 5 if suffix > 1 else 0
                    full_output_path = (
                        full_output_path.parent /
                        f'{full_output_path.stem[:-offset]}-{suffix:04d}{full_output_path.suffix}')
                    suffix += 1
            cmd = ('ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i',
                   temp_concat.name, '-c', 'copy', str(full_output_path))
            log.debug('Concatenating with: %s', ' '.join(quote(x) for x in cmd))
            sp.run(cmd, check=True, capture_output=True)
            for path in to_be_merged:
                path.unlink()
            for path in send_to_waste:
                send2trash(path)
                log.debug('Sent to wastebin: %s', path)


def hlg_to_sdr(input_file: StrPath,
               crf: int = 20,
               output_codec: Literal['libx265', 'libx264'] = 'libx265',
               output_file: StrPath | None = None,
               input_args: Sequence[str] | None = None,
               output_args: Sequence[str] | None = None,
               *,
               delete_after: bool = False,
               fast: bool = False) -> None:
    """Convert a HLG HDR video to SDR."""
    input_file = Path(input_file)
    vf = ((
        'zscale=t=linear:npl=100,'
        'format=gbrpf32le,'
        'zscale=p=bt709,'
        'tonemap=tonemap=hable:desat=0,'
        'zscale=t=bt709:m=bt709:r=tv,'
        'format=yuv420p'
    ) if fast else (
        'zscale=tin=arib-std-b67:min=bt2020nc:pin=bt2020:rin=tv:t=arib-std-b67:m=bt2020nc:p=bt2020:'
        'r=tv,'
        'zscale=t=linear:npl=100,'
        'format=gbrpf32le,'
        'zscale=p=bt709,'
        'tonemap=tonemap=hable:desat=0,'
        'zscale=t=bt709:m=bt709:r=tv,'
        'format=yuv420p'))
    output_file = str(output_file) if output_file else str(
        input_file.parent / f'{input_file.stem}-sdr{input_file.suffix}')
    cmd = ('ffmpeg', '-hide_banner', '-y', *(input_args or []), '-i', str(input_file),
           *(output_args or []), '-c:v', output_codec,
           '-crf', str(crf), '-vf', vf, '-acodec', 'copy', '-movflags', '+faststart',
           str(output_file) if output_file else f'{input_file.stem}-sdr{input_file.suffix}')
    log.debug('Running: %s', ' '.join(quote(x) for x in cmd))
    sp.run(cmd, check=True, capture_output=True)
    if delete_after:
        send2trash(input_file)
        log.debug('Sent to wastebin: %s', input_file)
