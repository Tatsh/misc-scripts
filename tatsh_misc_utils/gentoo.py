from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import Path
import logging
import re

from .typing import StrPath

DEFAULT_ACTIVE_KERNEL_NAME = 'linux'
DEFAULT_KERNEL_LOCATION = '/usr/src'
DEFAULT_MODULES_PATH = '/lib/modules/'

log = logging.getLogger(__name__)


class InvalidActiveKernelSourcePath(Exception):
    def __init__(self, source_path: StrPath) -> None:
        super().__init__(f'{source_path} is not a symbolic link.')


def clean_old_kernels_and_modules(
        path: StrPath = DEFAULT_KERNEL_LOCATION,
        modules_path: StrPath = DEFAULT_MODULES_PATH,
        active_kernel_name: str = DEFAULT_ACTIVE_KERNEL_NAME) -> Iterator[str]:
    """
    Remove inactive kernels and modules.

    By default, removes old Linux sources from ``/usr/src``.

    Parameters
    ----------
    path : StrPath
        Location where kernel sources are installed. Defaults to ``/usr/src``.

    modules_path : StrPath
        Location where modules get installed, such as ``/lib/modules``.

    active_kernel_name : str
        Kernel name like ``'linux'``.

    Yields
    ------
    str
        Deleted path.
    """
    path = Path(path)
    modules_path = Path(modules_path)
    loc = path / active_kernel_name
    if not loc.exists():
        raise FileNotFoundError
    if not loc.is_symlink():
        raise InvalidActiveKernelSourcePath(loc)
    v = re.sub(rf'^{DEFAULT_ACTIVE_KERNEL_NAME}-', '', str(loc.readlink()))
    current_version = f'{active_kernel_name}-{v}'
    version_pat = f'*{v}*'
    for d in modules_path.glob('*'):
        if d.is_dir() and not fnmatch(str(d), version_pat):
            d.rmdir()
            yield str(d)
    for d in path.glob(f'{active_kernel_name}-*'):
        if d.is_dir() and d.name != current_version:
            d.rmdir()
            yield str(d)
