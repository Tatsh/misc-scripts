from struct import pack
import enum


class Weight(enum.IntEnum):
    FW_BLACK = 900
    FW_BOLD = 700
    FW_DEMIBOLD = 600
    FW_DONTCARE = 0
    FW_EXTRABOLD = 800
    FW_EXTRALIGHT = 200
    FW_HEAVY = 900
    FW_LIGHT = 300
    FW_MEDIUM = 500
    FW_NORMAL = 400
    FW_REGULAR = 400
    FW_SEMIBOLD = 600
    FW_THIN = 100
    FW_ULTRABOLD = 800
    FW_ULTRALIGHT = 200


class ClipPrecision(enum.IntEnum):
    CLIP_CHARACTER_PRECIS = 0x1
    CLIP_DEFAULT_PRECIS = 0x0
    CLIP_DFA_DISABLE = 0x40
    CLIP_EMBEDDED = 0x80
    CLIP_LH_ANGLES = 0x10
    CLIP_MASK = 0xF
    CLIP_STROKE_PRECIS = 0x2
    CLIP_TT_ALWAYS = 0x20


class CharacterSet(enum.IntEnum):
    ANSI_CHARSET = 0
    ARABIC_CHARSET = 178
    BALTIC_CHARSET = 186
    CHINESEBIG5_CHARSET = 136
    DEFAULT_CHARSET = 1
    EE_CHARSET = 238
    GB2312_CHARSET = 134
    GREEK_CHARSET = 161
    HANGUL_CHARSET = 129
    HEBREW_CHARSET = 177
    JOHAB_CHARSET = 130
    MAC_CHARSET = 77
    OEM_CHARSET = 255
    RUSSIAN_CHARSET = 204
    SHIFTJIS_CHARSET = 128
    SYMBOL_CHARSET = 2
    THAI_CHARSET = 222
    TURKISH_CHARSET = 162
    VIETNAMESE_CHARSET = 163


class OutputPrecision(enum.IntEnum):
    OUT_CHARACTER_PRECIS = 2
    OUT_DEFAULT_PRECIS = 0
    OUT_DEVICE_PRECIS = 5
    OUT_OUTLINE_PRECIS = 8
    OUT_PS_ONLY_PRECIS = 10
    OUT_RASTER_PRECIS = 6
    OUT_SCREEN_OUTLINE_PRECIS = 9
    OUT_STRING_PRECIS = 1
    OUT_STROKE_PRECIS = 3
    OUT_TT_ONLY_PRECIS = 7
    OUT_TT_PRECIS = 4


class Pitch(enum.IntEnum):
    DEFAULT_PITCH = 0x0
    FIXED_PITCH = 0x01
    MONO_FONT = 0x08
    VARIABLE_PITCH = 0x02


class Family(enum.IntEnum):
    FF_DECORATIVE = 0x50
    FF_DONTCARE = 0x0
    FF_MODERN = 0x30
    FF_ROMAN = 0x10
    FF_SCRIPT = 0x40
    FF_SWISS = 0x20


class Quality(enum.IntEnum):
    ANTIALIASED_QUALITY = 4
    CLEARTYPE_NATURAL_QUALITY = 6
    CLEARTYPE_QUALITY = 5
    DEFAULT_QUALITY = 0
    DRAFT_QUALITY = 1
    NONANTIALIASED_QUALITY = 3
    PROOF_QUALITY = 2


class Field(enum.StrEnum):
    CaptionFont = 'CaptionFont'
    IconFont = 'IconFont'
    MenuFont = 'MenuFont'
    MessageFont = 'MessageFont'
    SmCaptionFont = 'SmCaptionFont'
    StatusFont = 'StatusFont'


LF_FULLFACESIZE = 64
DEFAULT_DPI = 72
MAX_LINE_LENGTH = 78


class NameTooLong(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(self, f'{name} length exceeds 64 characters.')


def make_font_entry(field: Field,
                    name: str = '',
                    *,
                    char_set: CharacterSet = CharacterSet.DEFAULT_CHARSET,
                    clip_precision: ClipPrecision = ClipPrecision.CLIP_DEFAULT_PRECIS,
                    default_setting: bool = False,
                    header: bool = False,
                    dpi: int = 96,
                    escapement: int = 0,
                    font_size_pt: int = 9,
                    italic: bool = False,
                    orientation: int = 0,
                    out_precision: OutputPrecision = OutputPrecision.OUT_DEFAULT_PRECIS,
                    pitch_and_family: int = Pitch.VARIABLE_PITCH | Family.FF_SWISS,
                    quality: Quality = Quality.DEFAULT_QUALITY,
                    strike_out: bool = False,
                    underline: bool = False,
                    weight: Weight = Weight.FW_NORMAL,
                    width: int = 0) -> str:
    r"""
    Generate a string for a ``.reg`` file to set a font in ``HKEY_CURRENT_USER\Control Panel\Desktop\WindowMetrics``. 

    This is used to set the font for the caption, icon, menu, message, small caption, and status
    fonts. The font name must be less than 64 characters.

    See `LOGFONTW (wingdi.h) - Win32 apps <https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-logfontw>`
    for more information.

    Parameters
    ----------
    field : Field
        The field name to use in the registry.
    name : str
        The name of the font.
    char_set : CharacterSet
        The character set to use.
    clip_precision : ClipPrecision
        The clip precision to use.
    default_setting : bool
        If ``True``, the header will use the ``HKEY_USERS\.Default`` key. Only applies when
        ``header`` is ``True``.
    header : bool
        If ``True``, the header will be included in the output.
    dpi : int
        The DPI to use.
    escapement : int
        The escapement to use.
    font_size_pt : int
        The font size in points.
    italic : bool
        If ``True``, the font will be italic.
    orientation : int
        The orientation to use.
    out_precision : OutputPrecision
        The output precision to use.
    pitch_and_family : int
        The pitch and family to use.
    quality : Quality
        The quality to use.
    strike_out : bool
        If ``True``, the font will be struck out.
    underline : bool
        If ``True``, the font will be underlined.
    weight : Weight
        The weight of the font.
    width : int
        The width of the font. This is usually left as ``0``.

    Returns
    -------
    str : A string composed of multiple lines for use in a ``.reg`` file.
    """  # noqa: E501
    if len(name) > LF_FULLFACESIZE:
        raise NameTooLong(name)
    packed = pack('<5l8b64s', -((font_size_pt * dpi) // DEFAULT_DPI), width, escapement,
                  orientation, weight, italic, underline, strike_out, char_set, out_precision,
                  clip_precision, quality, pitch_and_family,
                  name[:LF_FULLFACESIZE].encode('utf-16le').ljust(LF_FULLFACESIZE, b'\0'))
    lines: list[str] = []
    line = f'"{field}"=hex:'
    for n in packed:
        line += f'{n:02x},'
        lc = len(lines)
        if ((lc == 0 and len(line) == MAX_LINE_LENGTH)
                or (lc > 0 and len(line) == (MAX_LINE_LENGTH - 1))):
            line += '\\'
            lines.append(line)
            line = '  '
    lines.append(line.rstrip(','))
    return '\n'.join(
        (*((r'HKEY_USERS\.Default\Control Panel\Desktop\WindowMetrics' if default_setting else
            r'HKEY_CURRENT_USER\Control Panel\Desktop\WindowMetrics') if header else '',), *lines))
