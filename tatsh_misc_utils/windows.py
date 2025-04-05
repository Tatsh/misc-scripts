from struct import pack
import enum


class Weight(enum.IntEnum):
    """
    The weight of the font in the range 0 through 1000.

    For example, 400 is normal and 700 is bold. If this value is zero, a default weight is used.
    These values are provided for convenience.
    """
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
    """
    The clipping precision.

    The clipping precision defines how to clip characters that are partially
    outside the clipping region.
    """
    CLIP_CHARACTER_PRECIS = 0x1
    """Not used."""
    CLIP_DEFAULT_PRECIS = 0x0
    """Specifies default clipping behaviour."""
    CLIP_DFA_DISABLE = 0x40
    """
    Windows XP SP1: Turns off font association for the font. Note that this flag is not guaranteed
    to have any effect on any platform after Windows Server 2003.
    """
    CLIP_EMBEDDED = 0x80
    """You must specify this flag to use an embedded read-only font."""
    CLIP_LH_ANGLES = 0x10
    """
    When this value is used, the rotation for all fonts depends on whether the orientation of the
    coordinate system is left-handed or right-handed.If not used, device fonts always rotate
    counter-clockwise, but the rotation of other fonts is dependent on the orientation of the
    coordinate system.
    """
    CLIP_MASK = 0xF
    """Not used."""
    CLIP_STROKE_PRECIS = 0x2c
    """
    Not used by the font mapper, but is returned when raster, vector, or TrueType fonts are
    enumerated. For compatibility, this value is always returned when enumerating fonts.
    """
    CLIP_TT_ALWAYS = 0x20
    """Not used."""


class CharacterSet(enum.IntEnum):
    """
    The character set.

    Fonts with other character sets may exist in the operating system. If an application uses a font
    with an unknown character set, it should not attempt to translate or interpret strings that are
    rendered with that font.

    This parameter is important in the font mapping process. To ensure consistent results when
    creating a font, do not specify ``OEM_CHARSET`` or ``DEFAULT_CHARSET``. If you specify a
    typeface name in the ``lfFaceName`` member, make sure that the ``lfCharSet`` value matches the
    character set of the typeface specified in ``lfFaceName``.
    """
    ANSI_CHARSET = 0
    ARABIC_CHARSET = 178
    BALTIC_CHARSET = 186
    CHINESEBIG5_CHARSET = 136
    DEFAULT_CHARSET = 1
    """
    DEFAULT_CHARSET is set to a value based on the current system locale. For example, when the
    system locale is English (United States), it is set as ``ANSI_CHARSET``.
    """
    EE_CHARSET = 238
    GB2312_CHARSET = 134
    GREEK_CHARSET = 161
    HANGUL_CHARSET = 129
    HEBREW_CHARSET = 177
    JOHAB_CHARSET = 130
    MAC_CHARSET = 77
    OEM_CHARSET = 255
    """Specifies a character set that is operating-system dependent."""
    RUSSIAN_CHARSET = 204
    SHIFTJIS_CHARSET = 128
    SYMBOL_CHARSET = 2
    THAI_CHARSET = 222
    TURKISH_CHARSET = 162
    VIETNAMESE_CHARSET = 163


class OutputPrecision(enum.IntEnum):
    """
    The output precision.

    The output precision defines how closely the output must match the requested font's height,
    width, character orientation, escapement, pitch, and font type.
    """
    OUT_CHARACTER_PRECIS = 2
    """Not used."""
    OUT_DEFAULT_PRECIS = 0
    """Specifies the default font mapper behaviour."""
    OUT_DEVICE_PRECIS = 5
    """
    Instructs the font mapper to choose a Device font when the system contains multiple fonts with
    the same name.
    """
    OUT_OUTLINE_PRECIS = 8
    """
    This value instructs the font mapper to choose from TrueType and other outline-based fonts.
    """
    OUT_PS_ONLY_PRECIS = 10
    """
    Instructs the font mapper to choose from only PostScript fonts. If there are no PostScript
    fonts installed in the system, the font mapper returns to default behaviour.
    """
    OUT_RASTER_PRECIS = 6
    """
    Instructs the font mapper to choose a raster font when the system contains multiple fonts with
    the same name.
    """
    OUT_STRING_PRECIS = 1
    """
    This value is not used by the font mapper, but it is returned when raster fonts are enumerated.
    """
    OUT_STROKE_PRECIS = 3
    """
    This value is not used by the font mapper, but it is returned when TrueType, other
    outline-based fonts, and vector fonts are enumerated.
    """
    OUT_TT_ONLY_PRECIS = 7
    """
    Instructs the font mapper to choose from only TrueType fonts. If there are no TrueType fonts
    installed in the system, the font mapper returns to default behaviour.
    """
    OUT_TT_PRECIS = 4
    """
    Instructs the font mapper to choose a TrueType font when the system contains multiple fonts with
    the same name.
    """


class Pitch(enum.IntEnum):
    """
    The pitch and family of the font.

    In the ``iPitchAndFamily`` argument to ``CreateFontW``, these values represent the two low-order
    bits.
    """
    DEFAULT_PITCH = 0x0
    FIXED_PITCH = 0x01
    MONO_FONT = 0x08
    VARIABLE_PITCH = 0x02


class Family(enum.IntEnum):
    """
    Font Family.

    Font families describe the look of a font in a general way. They are intended for specifying
    fonts when the exact typeface desired is not available.

    In the ``iPitchAndFamily`` argument to ``CreateFontW``, these values represent bits 4 through 7.
    """
    FF_DECORATIVE = 0x50
    """Novelty fonts. Old English is an example."""
    FF_DONTCARE = 0x0
    """Use default font."""
    FF_MODERN = 0x30
    """
    Fonts with constant stroke width (monospace), with or without serifs. Monospace fonts are
    usually modern. Pica, Elite, and CourierNew are examples.
    """
    FF_ROMAN = 0x10
    """Fonts with variable stroke width (proportional) and with serifs. MS Serif is an example."""
    FF_SCRIPT = 0x40
    """Fonts designed to look like handwriting. Script and Cursive are examples."""
    FF_SWISS = 0x20
    """
    Fonts with variable stroke width (proportional) and without serifs. MS Sans Serif is an
    example.
    """


class Quality(enum.IntEnum):
    """
    Quality.

    The output quality defines how carefully the graphics device interface (GDI) must attempt to
    match the logical-font attributes to those of an actual physical font.

    If neither ``ANTIALIASED_QUALITY`` nor ``NONANTIALIASED_QUALITY`` is selected, the font is
    antialiased only if the user chooses smooth screen fonts in Control Panel.
    """
    ANTIALIASED_QUALITY = 4
    """
    Font is always antialiased if the font supports it and the size of the font is not too small or
    too large.
    """
    CLEARTYPE_QUALITY = 5
    """If set, text is rendered (when possible) using ClearType antialiasing method."""
    DEFAULT_QUALITY = 0
    """Appearance of the font does not matter."""
    DRAFT_QUALITY = 1
    """
    Appearance of the font is less important than when ``PROOF_QUALITY`` is used. For GDI raster
    fonts, scaling is enabled, which means that more font sizes are available, but the quality may
    be lower. Bold, italic, underline, and strikeout fonts are synthesized if necessary.
    """
    NONANTIALIASED_QUALITY = 3
    """Font is never antialiased."""
    PROOF_QUALITY = 2
    """
    Character quality of the font is more important than exact matching of the logical-font
    attributes. For GDI raster fonts, scaling is disabled and the font closest in size is chosen.
    Although the chosen font size may not be mapped exactly when ``PROOF_QUALITY`` is used, the
    quality of the font is high and there is no distortion of appearance. Bold, italic, underline,
    and strikeout fonts are synthesized if necessary.
    """


class Field(enum.StrEnum):
    """Font field names in the registry."""
    CaptionFont = 'CaptionFont'
    """Font used in window title bars."""
    IconFont = 'IconFont'
    """Font used for icons in Explorer and similar views."""
    MenuFont = 'MenuFont'
    """Font used for menus."""
    MessageFont = 'MessageFont'
    """Font used in message boxes and many other places."""
    SmCaptionFont = 'SmCaptionFont'
    StatusFont = 'StatusFont'
    """Font used in status bars."""


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
    height = -((font_size_pt * dpi) // DEFAULT_DPI)
    packed = pack('<5l8b64s', height, width, escapement, orientation, weight, italic, underline,
                  strike_out, char_set, out_precision, clip_precision, quality, pitch_and_family,
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
