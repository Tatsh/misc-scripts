#!/usr/bin/env python
from typing import Any
import re
import sys

try:
    from youtube_dl.utils import sanitize_filename
except ImportError as e:

    def sanitize_filename(*args: Any, **kwargs: Any) -> str:
        raise ImportError('youtube_dl.utils not found') from e


__all__ = ('main', )


def main(s: str) -> int:
    try:
        r = sanitize_filename(s, restricted=True)
    except (ImportError, IndexError):
        return 1
    r = r.strip()
    if not r:
        return 1
    print(re.sub(r'[_\-]+', '-', r.lower()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
