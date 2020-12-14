#!/usr/bin/env python
from copy import deepcopy
from datetime import datetime
from os.path import expanduser
from typing import Literal, Optional, Tuple, TypedDict, cast
from urllib.parse import unquote as urldecode
import re
import sqlite3
import sys

from typing_extensions import Final

from ..utils import setup_logging_stderr

CREATION_UTC: Final[int] = int(
    (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds() * (10**7))
COLUMNS: Final[Tuple[str,
                     ...]] = ('creation_utc', 'host_key', 'name', 'value',
                              'path', 'expires_utc', 'secure', 'httponly',
                              'has_expires', 'persistent', 'last_access_utc')
LEN_COLUMNS: Final[int] = len(COLUMNS)
DB_PATHS: Final[Tuple[str, ...]] = (
    expanduser('~/.config/chromium/Default/Cookies'),
    expanduser('~/Library/Application Support/Google/Chrome/Cookies'))
REGEX: Final[str] = (
    r'^(?P<host_key>.*)\t(?P<httponly>TRUE|FALSE)\t(?P<path>.*)' +
    r'\t(?P<secure>TRUE|FALSE)\t(?P<expires_utc>\d+(\.\d+)?)' +
    r'\t(?P<name>.*)\t(?P<value>.*)\n?')


class MatchDict(TypedDict):
    expires_utc: str
    host_key: str
    httponly: Literal['TRUE', 'FALSE']
    name: str
    path: str
    secure: Literal['TRUE', 'FALSE']
    value: str


def main() -> int:
    log = setup_logging_stderr(verbose=True)
    try:
        cookies_txt = sys.argv[1]
    except IndexError:
        log.info('Usage: %s COOKIES_TXT_FILE', sys.argv[0])
        return 1
    conn: Optional[sqlite3.Connection] = None
    last_exc: Optional[Exception] = None
    for p in DB_PATHS:
        try:
            with open(p, 'rb'):
                pass
            conn = sqlite3.connect(p, detect_types=sqlite3.PARSE_COLNAMES)
            break
        except (FileNotFoundError, sqlite3.OperationalError) as e:
            last_exc = e
    if not conn and last_exc:
        raise last_exc
    if not conn:
        raise RuntimeError('Failed to connect to database')
    try:
        with open(cookies_txt) as f:
            i = 0
            lines = f.readlines()
            c = conn.cursor()
            for line in lines:
                match = re.match(REGEX, line)
                if not match:
                    log.debug('Skipping line: %s', line.strip())
                    continue
                dic = cast(MatchDict, deepcopy(match.groupdict()))
                expires_utc = int(float(dic['expires_utc'])) * (10**7)
                dic['value'] = urldecode(dic['value'])
                dic['path'] = urldecode(dic['path'])
                has_expires = persistent = 1
                if expires_utc == 0:
                    has_expires = 0
                    persistent = 0
                httponly = 1 if dic['httponly'] == 'TRUE' else 0
                secure = 1 if dic['secure'] == 'TRUE' else 0
                c.execute(
                    ('DELETE FROM cookies WHERE host_key = ? AND name = ? '
                     'AND path = ?'), (
                         dic['host_key'],
                         dic['name'],
                         dic['path'],
                     ))
                cols = ','.join(COLUMNS)
                col_args = ('?,' * LEN_COLUMNS)[:-1]
                t = (CREATION_UTC + i, dic['host_key'], dic['name'],
                     dic['value'], dic['path'], expires_utc, secure, httponly,
                     has_expires, persistent, CREATION_UTC)
                c.execute(f'INSERT INTO cookies ({cols}) VALUES({col_args})',
                          t)
                i += 1
    except FileNotFoundError:
        log.error('Cookies file %s specified does not exist', cookies_txt)
    finally:
        conn.commit()
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
