#!/usr/bin/env python
from pathlib import Path
from typing import Dict
import plistlib
import sys

from typing_extensions import Final

from ..utils import setup_logging_stdout

__all__ = ('main', )

HIGH_RES_KEY: Final[str] = 'NSHighResolutionCapable'


def main() -> int:
    log = setup_logging_stdout()
    for fin in sys.argv[1:]:
        p = Path(fin).joinpath('Contents', 'Info.plist')
        if not p.exists():
            log.warning('Skipping %s (Info.plist not found)', fin)
            continue
        with p.open('rb') as f:
            data: Dict[str, bool] = plistlib.load(f)
            data[HIGH_RES_KEY] = True
        with p.open('wb') as f:
            plistlib.dump(data, f, sort_keys=False)
        log.info('Rewrote Info.plist for %s', fin)
        log.debug('Running `touch "%s"`', fin)
        Path(fin).touch()
    return 0


if __name__ == '__main__':
    sys.exit(main())
