from functools import cache
from io import BytesIO
from pathlib import Path
from typing import cast

import requests

from .typing import StrPath


def fix_chromium_pwa_icon(config_path: StrPath,
                          app_id: str,
                          icon_src_uri: str,
                          profile: str = 'Default',
                          *,
                          masked: bool = False,
                          monochrome: bool = False) -> None:
    """
    Fix a Chromium PWA icon that failed to sync.

    See Also
    --------
    https://issues.chromium.org/issues/40595456
    """
    from PIL import Image  # noqa: PLC0415
    config_path = Path(config_path) / profile / 'Web Applications' / app_id
    r = requests.get(icon_src_uri, timeout=15)
    r.raise_for_status()
    img = Image.open(BytesIO(r.content))
    width, height = img.size
    if width != height:
        msg = 'Icon is not square.'
        raise ValueError(msg)
    sizes = reversed([1 << x for x in range(4, min(10, width.bit_length()))])
    for size in sizes:
        img.resize((size, size), Image.LANCZOS).save(config_path / 'Icons' / f'{size}.png')
    if masked:
        for size in sizes:
            img.resize((size, size),
                       Image.LANCZOS).save(config_path / 'Icons Maskable' / f'{size}.png')
    if monochrome:
        for size in sizes:
            img.resize((size, size),
                       Image.LANCZOS).save(config_path / 'Icons Monochrome' / f'{size}.png')


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
