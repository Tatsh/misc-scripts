"""Uncategorised utilities."""
from collections.abc import Iterable
from math import trunc
import re

__all__ = ('add_cdda_times',)

ZERO_TO_59 = '|'.join(f'{x:02d}' for x in range(60))
ZERO_TO_74 = '|'.join(f'{x:02d}' for x in range(75))
TIMES_RE = re.compile(f'^({ZERO_TO_59}):({ZERO_TO_59}):({ZERO_TO_74})$')
MAX_FRAMES = 75
MAX_MINUTES = 99
MAX_SECONDS = 60


def add_cdda_times(times: Iterable[str] | None) -> str | None:
    if not times:
        return None
    total_ms = 0.0
    for time in times:
        if not (res := re.match(TIMES_RE, time)):
            return None
        minutes, seconds, frames = [float(x) for x in res.groups()]
        total_ms += (minutes *
                     (MAX_SECONDS - 1) * 1000) + (seconds * 1000) + (frames * 1000) / MAX_FRAMES
    minutes = total_ms / (MAX_SECONDS * 1000)
    remainder_ms = total_ms % (MAX_SECONDS * 1000)
    seconds = remainder_ms / 1000
    remainder_ms %= 1000
    frames = (remainder_ms * 1000 * MAX_FRAMES) / 1e6
    if minutes > MAX_MINUTES or seconds > (MAX_SECONDS - 1) or frames > MAX_FRAMES:
        return None
    return f'{trunc(minutes):02d}:{trunc(seconds):02d}:{trunc(frames):02d}'
