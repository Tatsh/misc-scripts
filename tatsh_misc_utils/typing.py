from enum import IntEnum
from os import PathLike
from typing import Annotated, Any, Literal
import os
import typing

__all__ = ('CDStatus', 'DecodeErrorsOption', 'FileDescriptorOrPath', 'INCITS38Code',
           'StrOrBytesPath', 'StrPath', 'UNIXStrPath', 'contains_type_path_like_str')

DecodeErrorsOption = Literal['ignore', 'replace', 'strict']
INCITS38Code = Literal['AK', 'AL', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'FM', 'GA',
                       'GU', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MH',
                       'MI', 'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV',
                       'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'PW', 'RI', 'SC', 'SD', 'TN', 'TX', 'UM',
                       'UT', 'VA', 'VI', 'VT', 'WA', 'WI', 'WV', 'WY']
StrOrBytesPath = str | bytes | PathLike[str] | PathLike[bytes]
StrPath = str | PathLike[str]
"""String or ``PathLike[str]``."""
FileDescriptorOrPath = int | StrOrBytesPath
UNIXStrPath = Annotated[StrPath, 'unix']
StrPathMustExist = Annotated[StrPath, 'must_exist']


class CDStatus(IntEnum):
    DISC_OK = 4
    DRIVE_NOT_READY = 3
    NO_DISC = 1
    NO_INFO = 0
    TRAY_OPEN = 2


def contains_type_path_like_str(type_hints: Any) -> bool:
    return os.PathLike[str] in typing.get_args(type_hints)