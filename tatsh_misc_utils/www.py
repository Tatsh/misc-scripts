from collections.abc import Iterator, Sequence
from html import escape
from itertools import chain
from os import getxattr, scandir
from pathlib import Path
from typing import cast
import contextlib
import plistlib

from .string import hexstr2bytes
from .system import IS_LINUX
from .typing import FileDescriptorOrPath, StrPath

__all__ = ('generate_html_dir_tree', 'where_from')

KEY_ORIGIN_URL = 'user.xdg.origin.url'
KEY_WHERE_FROMS = 'com.apple.metadata:kMDItemWhereFroms'


def where_from(file: FileDescriptorOrPath, *, webpage: bool = False) -> str | None:
    index = 1 if webpage else 0
    attr_value = getxattr(file, KEY_ORIGIN_URL if IS_LINUX else KEY_WHERE_FROMS).decode()
    if not IS_LINUX:
        return cast(Sequence[str], plistlib.loads(hexstr2bytes(attr_value)))[index]
    return attr_value


def generate_html_dir_tree(start_dir: StrPath,
                           *,
                           follow_symlinks: bool = False,
                           depth: int = 2) -> str:
    """Generate a HTML directory listing."""
    def recurse_cwd(path: Path, _cur_depth: int = 0) -> Iterator[str]:
        for entry in sorted(sorted(scandir(path), key=lambda x: x.name),
                            key=lambda x: not x.is_dir(follow_symlinks=follow_symlinks)):
            if (entry.is_dir(follow_symlinks=follow_symlinks) and _cur_depth < depth):
                yield ('<li class="dir mui--text-dark mui--text-body2"><details><summary>'
                       f'<code>{escape(entry.name)}/</code></summary><ul>')
                yield from recurse_cwd(Path(entry), _cur_depth=_cur_depth + 1)
                yield '</ul></details></li>'
            else:
                isd = entry.is_dir(follow_symlinks=follow_symlinks)
                class_ = 'file' if not isd else 'dir'
                slash = '' if not isd else '/'
                yield (
                    f'<li class="{class_} mui--text-dark mui--text-body1"><a class="mui--text-dark" '
                    f'href="./{entry.path}"><code>{escape(entry.name)}{slash}</code></a></li>')

    start_dir = Path(start_dir).resolve(strict=True)
    with contextlib.chdir(start_dir):
        title = start_dir.name
        files = ''.join(chain.from_iterable(recurse_cwd(start_dir)))
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contents of {title}/</title>
<link rel="stylesheet" href="https://cdn.muicss.com/mui-0.10.3/css/mui.min.css"
crossorigin="anonymous">
<style>
ul {{
    list-style: none;
    padding-inline-start: 1em;
}}
.dir {{
    cursor: pointer;
}}
.mui-appbar {{
    margin-bottom: 2em;
}}
</style>
</head>
<body>
<header class="mui-appbar mui--z1">
<div class="mui-container-fluid">
<h1 class="mui--text-title">Contents of {title}</h1>
</div>
</header>
<div class="mui-container-fluid">
<ul>{files}</ul>
</div>
</body>
</html>"""
