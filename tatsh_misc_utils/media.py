"""Media-related utility functions."""
from collections.abc import Sequence
import logging
import subprocess as sp

__all__ = ('is_audio_input_format_supported', 'supported_audio_input_formats')

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
            if 'cannot set sample format 0x' in all_output or f'{rates} Hz' not in all_output:
                continue
            ret.append((format_, rate))
    return tuple(ret)


def is_audio_input_format_supported(
        input_device: str,
        format: str,  # noqa: A002
        rate: int) -> bool:
    return bool(supported_audio_input_formats(input_device, formats=(format,), rates=(rate,)))
