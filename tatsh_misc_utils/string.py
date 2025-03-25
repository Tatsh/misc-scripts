# ruff: noqa: RUF001
from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, cast
import os
import re
import string

from yt_dlp.utils import sanitize_filename
import requests

from .itertools import chunks
from .typing import StrPath, assert_not_none

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

__all__ = ('fullwidth_to_narrow', 'generate_chrome_user_agent', 'get_latest_chrome_major_version',
           'hexstr2bytes', 'hexstr2bytes_generator', 'is_ascii', 'is_url', 'sanitize', 'slugify',
           'strip_ansi', 'strip_ansi_if_no_colors', 'underscorize', 'unix_path_to_wine')

ORD_MAX = 128
STRIP_ANSI_PATTERN = re.compile(r'\x1B\[\d+(;\d+){0,2}m')


@cache
def strip_ansi(o: str) -> str:
    """
    Remove ANSI escape sequences from `o`.

    As defined by ECMA-048 in http://www.ecma-international.org/publications/files/ECMA-ST/Ecma-048.

    Taken from https://github.com/ewen-lbh/python-strip-ansi/ due to installation issues with
    Poetry.
    """
    return STRIP_ANSI_PATTERN.sub('', o)


def strip_ansi_if_no_colors(s: str) -> str:
    """
    Strip ANSI colour-codes if the ``NO_COLOR`` environment variable is set.

    See https://no-color.org/.
    """
    return strip_ansi(s) if os.environ.get('NO_COLOR') else s


@cache
def underscorize(s: str) -> str:
    """Replace all space-type characters with ``_``."""
    return re.sub(r'\s+', '_', s)


@cache
def is_ascii(s: Sequence[str]) -> bool:
    """Check if a string consists of only ASCII characters."""
    return len(s) == len(''.join(y for y in s if ord(y) < ORD_MAX))


def hexstr2bytes_generator(s: str) -> Iterator[int]:
    """Convert a hex string such as ``"01020a"`` to integers."""
    for hex_num in chunks(s, 2):
        yield int(hex_num, 16)


def hexstr2bytes(s: str) -> bytes:
    """Convert a hex string such as ``"01020a"`` to its bytes form (``0x1 0x2 0x10)``)."""
    return bytes(hexstr2bytes_generator(s))


@cache
def unix_path_to_wine(path: StrPath) -> str:
    """
    Convert a UNIX path to an absolute Wine path.

    If the path does not exist, the output will be the current path and the path passed in combined.

    The output path will begin at letter ``Z:``. Other drive letters are not supported.

    Parameters
    ----------
    path : StrPath
        Path to convert.

    Returns
    -------
    str
        Window-style Wine absolute path.
    """
    try:
        path = Path(path).resolve(strict=True)
    except FileNotFoundError:
        path = Path.cwd() / path
    return f'Z:{path}'.replace('/', '\\')


@cache
def get_last_chrome_major_version() -> str:
    """
    Get last major Chrome version from the profile directory.
    
    Tries the following, in order:

    * Chrome Beta
    * Chrome
    * Chrome Canary
    * Chromium

    Returns
    -------
    str
        If no ``Last Version`` file is found, returns empty string.
    """
    for location in ('~/.config/google-chrome-beta', '~/AppData/Local/Google/Chrome Beta/User Data'
                     '~/Library/Application Support/Google/Chrome Beta', '~/.config/google-chrome',
                     '~/AppData/Local/Google/Chrome/User Data',
                     '~/Library/Application Support/Google/Chrome',
                     '~/.config/google-chrome-unstable',
                     '~/AppData/Local/Google/Chrome Canary/User Data',
                     '~/Library/Application Support/Google/Chrome Canary', '~/.config/chromium',
                     '~/AppData/Local/Google/Chromium/User Data',
                     '~/Library/Application Support/Google/Chromium'):
        if (p := (Path(location).expanduser() / 'Last Version')).exists():
            return p.read_text().split('.', 1)[0]
    return ''


@cache
def get_latest_chrome_major_version() -> str:
    """Get the latest Chrome major version."""
    return cast(
        'str',
        requests.get(
            ('https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/'
             'versions'),
            timeout=5).json()['versions'][0]['version'].split('.')[0])


@cache
def generate_chrome_user_agent(os: str = 'Windows NT 10.0; Win64; x64') -> str:
    """Get a Chrome user agent."""
    last_major = get_last_chrome_major_version() or get_latest_chrome_major_version()
    return (f'Mozilla/5.0 ({os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{last_major}.0.0.0'
            ' Safari/537.36')


@cache
def sanitize(s: str, *, restricted: bool = True) -> str:
    """
    Transform a string to a 'sanitised' form.

    Parameters
    ----------
    s : str
        String to transform.
    restricted : bool
        If ``True``, use a restricted form. This is suitable for filenames on Windows.

    Returns
    -------
    str
        Returns a transformed string, which will be at minimum ``'_'``.
    """
    return re.sub(
        r'([a-z0-9])\-s\-', r'\1s-',
        re.sub(r'\.-', '-',
               re.sub(r'[_\-]+', '-',
                      sanitize_filename(s, restricted=restricted).lower())))


@cache
def is_url(filename: str) -> bool:
    """
    Detect if ``filename`` is a URL.

    This is the same method mpv uses to decide this.
    """
    parts = filename.split('://', 1)
    if len(parts) < 2:  # noqa: PLR2004
        return False
    # protocol prefix has no special characters => it's a URL
    return all(x in f'{string.ascii_letters}{string.digits}_' for x in parts[0])


def add_unidecode_custom_replacement(find: str, replace: str) -> None:
    """
    Add a custom replacement to the Unidecode library.

    Call this before calling ``unidecode()``.

    Notes
    -----
    Unidecode is GPL-only which makes anything calling into this significantly also GPL. If you do
    not intend to release GPL code, then you must use a different library such as
    `text-unidecode <https://github.com/kmike/text-unidecode>`_.
    """
    from unidecode import Cache, unidecode  # noqa: PLC0415
    unidecode(find)  # Force it to load the module
    codepoint = ord(find)
    section = codepoint >> 8
    position = codepoint % 256
    new_section = cast('list[str | None]',
                       (Cache[section] if isinstance(Cache[section], list) else
                        (list(assert_not_none(Cache[section])) if Cache[section] is not None else
                         [None for _ in range(position + 1)])))  # convert to mutable type
    assert len(new_section) > position
    new_section[position] = replace
    Cache[section] = new_section


FULLWIDTH_MAP = (
    ('　', ' '),
    ('…', '...'),
    ('！', '!'),
    ('？', '?'),
    ('～', '~'),
    ('（', '('),
    ('）', ')'),
    ('＂', '"'),
    ('＃', '#'),
    ('＄', '$'),
    ('％', '%'),
    ('＆', '&'),
    ('＇', "'"),
    ('＊', '*'),
    ('，', ','),
    ('－', '-'),
    ('．', '.'),
    ('／', '/'),
    ('０', '0'),
    ('１', '1'),
    ('２', '2'),
    ('３', '3'),
    ('４', '4'),
    ('５', '5'),
    ('６', '6'),
    ('７', '7'),
    ('８', '8'),
    ('９', '9'),
    ('：', ':'),
    ('；', ';'),
    ('＜', '<'),
    ('＝', '='),
    ('＞', '>'),
    ('？', '?'),
    ('＠', '@'),
    ('Ａ', 'A'),
    ('Ｂ', 'B'),
    ('Ｃ', 'C'),
    ('Ｄ', 'D'),
    ('Ｅ', 'E'),
    ('Ｆ', 'F'),
    ('Ｇ', 'G'),
    ('Ｈ', 'H'),
    ('Ｉ', 'I'),
    ('Ｊ', 'J'),
    ('Ｋ', 'K'),
    ('Ｌ', 'L'),
    ('Ｍ', 'M'),
    ('Ｎ', 'N'),
    ('Ｏ', 'O'),
    ('Ｐ', 'P'),
    ('Ｑ', 'Q'),
    ('Ｒ', 'R'),
    ('Ｓ', 'S'),
    ('Ｔ', 'T'),
    ('Ｕ', 'U'),
    ('Ｖ', 'V'),
    ('Ｗ', 'W'),
    ('Ｘ', 'X'),
    ('Ｙ', 'Y'),
    ('Ｚ', 'Z'),
    ('［', '['),
    ('＼', '\\'),
    ('］', ']'),
    ('＾', '^'),
    ('＿', '_'),
    ('｀', '`'),
    ('ａ', 'a'),
    ('ｂ', 'b'),
    ('ｃ', 'c'),
    ('ｄ', 'd'),
    ('ｅ', 'e'),
    ('ｆ', 'f'),
    ('ｇ', 'g'),
    ('ｈ', 'h'),
    ('ｉ', 'i'),
    ('ｊ', 'j'),
    ('ｋ', 'k'),
    ('ｌ', 'l'),
    ('ｍ', 'm'),
    ('ｎ', 'n'),
    ('ｏ', 'o'),
    ('ｐ', 'p'),
    ('ｑ', 'q'),
    ('ｒ', 'r'),
    ('ｓ', 's'),
    ('ｔ', 't'),
    ('ｕ', 'u'),
    ('ｖ', 'v'),
    ('ｗ', 'w'),
    ('ｘ', 'x'),
    ('ｙ', 'y'),
    ('ｚ', 'z'),
    ('｛', '{'),
    ('｜', '|'),
    ('｝', '}'),
    ('｟', '⸨'),
    ('｠', '⸩'),
    ('￠', '¢'),
    ('￡', '£'),
    ('￢', '¬'),
    ('￣', '‾'),
    ('￤', '|'),
    ('￥', '¥'),
    ('￦', '₩'),
)


@cache
def fullwidth_to_narrow(s: str) -> str:
    """
    Convert fullwidth characters in ``s`` to narrow or halfwidth.
    
    Unlike Unidecode this will convert ``'￥'`` to its halfwidth form ``'¥'``.
    """
    for find, replace in FULLWIDTH_MAP:
        s = s.replace(find, replace)
    return s


@cache
def slugify(s: str, *, no_lower: bool = False) -> str:
    """Slug string generator."""
    return re.sub(r'[-\s_]+', '-', re.sub(r'[^\w\s-]', '', s if no_lower else s.lower()).strip())


@cache
def is_roman_numeral(string: str) -> bool:
    """Check if a string is a Roman numeral."""
    if not string:
        return False
    return re.match(r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$', string,
                    re.IGNORECASE) is not None


@cache
def fix_apostrophes(word: str) -> str:
    """
    Fix letters around an apostrophe.
    
    Example: ``"Don'T"`` becomes ``"Don't"``.
    """
    if "'" not in word:
        return word
    return re.sub(r"[A-Za-z]+('[A-Za-z]+)?",
                  lambda mo: f'{mo.group(0)[0].upper()}{mo.group(0)[1:].lower()}', word)
