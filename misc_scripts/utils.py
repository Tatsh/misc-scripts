from functools import lru_cache
from os.path import basename
from typing import Callable, Optional, TextIO
import logging
import sys

__all__ = (
    'setup_logging',
    'setup_logging_stderr',
    'setup_logging_stdout',
)


def setup_logging(out: TextIO) -> Callable[..., logging.Logger]:
    @lru_cache()
    def func(name: Optional[str] = None,
             verbose: Optional[bool] = False) -> logging.Logger:
        name = name if name else basename(sys.argv[0])
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG if verbose else logging.INFO)
        channel = logging.StreamHandler(out)
        channel.setFormatter(logging.Formatter('%(message)s'))
        channel.setLevel(logging.DEBUG if verbose else logging.INFO)
        log.addHandler(channel)
        return log

    return func


setup_logging_stderr = setup_logging(sys.stderr)
setup_logging_stdout = setup_logging(sys.stdout)
