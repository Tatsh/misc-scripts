#!/usr/bin/env python
from collections.abc import Sequence
from pathlib import Path
from typing import Final, cast
import plistlib

from xattr import getxattr
import click

from .utils import IS_LINUX, hexstr2bytes

__all__ = ('where_from',)

KEY_ORIGIN_URL: Final[str] = 'user.xdg.origin.url'
KEY_WHERE_FROMS: Final[str] = 'com.apple.metadata:kMDItemWhereFroms'


def where_from(file: Path, *, webpage: bool = False) -> str | None:
    index = 1 if webpage else 0
    attr_value = getxattr(file, KEY_ORIGIN_URL if IS_LINUX else KEY_WHERE_FROMS).decode()
    if not IS_LINUX:
        attr_value = cast(Sequence[str], plistlib.loads(hexstr2bytes(attr_value)))[index]
    return attr_value


@click.command('Determine where downloaded files came from.')
@click.argument('files',
                metavar='FILE',
                nargs=-1,
                type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('-w', '--webpage', is_flag=True, help='Print the webpage URL (macOS only).')
def main(files: Sequence[str], *, webpage: bool = False) -> None:
    has_multiple = len(files) > 1
    for arg in files:
        if has_multiple:
            click.echo(f'{arg}: ', nl=False)
        click.echo(where_from(arg, webpage=webpage))
