"""Media-related utility functions."""
from collections.abc import Sequence
from datetime import datetime
from os import utime
from pathlib import Path
from shutil import copyfile
from typing import Any
import contextlib
import json
import logging
import re
import subprocess as sp
import tempfile

from .typing import StrPath

__all__ = ('add_info_json_to_media_file', 'ffprobe', 'get_info_json',
           'is_audio_input_format_supported', 'supported_audio_input_formats')

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
