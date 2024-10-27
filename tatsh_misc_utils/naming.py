from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING
import re

from .string import fix_apostrophes, is_roman_numeral
from .typing import assert_not_none

if TYPE_CHECKING:
    from collections.abc import Iterable

# non-strict, not including words like below, forms of to be, forms of
#   you/he/etc, or words like 'call'
STOP_WORDS = (
    'a',
    'an',
    'and',
    'at',
    'by',
    'de',  # mainly for Spanish and French
    'el',  # Spanish
    'feat',
    'featuring',
    'for',
    'from',
    'il',  # Italian
    'in',
    'into',
    'la',  # Spanish/French/Italian
    'lo',  # Italian
    'of',
    'off',
    'on',
    'or',
    'per',
    'por',  # Spanish
    # 'so',
    'te',  # Spanish/French
    # 'than',
    'the',
    # 'then',
    # 'this',
    'to',
    # 'too',
    'van',
    'via',
    'von',
    'vs',
    'with',
    'within',
    'without')
ENGLISH_ORDINAL_RE = r'(\d+)(st|nd|rd|th)'
ENGLISH_ABBREV = ('feat', 'mr', 'mrs', 'ms', 'vs')
"""English abbreviations for period removal."""
JAPANESE_PARTICLES = ('de', 'e', 'ga', 'ha', 'ka', 'kana', 'ne', 'ni', 'no', 'to', 'wa', 'wo')
"""Only really common ones."""
CHINESE_PARTICLES = ('de', 'ge', 'he', 'le', 'ma')
"""Only really common ones."""
ARABIC_STOPS = ('al', 'ala', 'alayhi', 'alayka', 'alayya', 'an', 'anhu', 'anka', 'anni', 'bi',
                'biha', 'bihi', 'bika', 'fi', 'fihi', 'fika', 'fiya', 'ila', 'ilayhi', 'ilayka',
                'ilayya', 'lahu', 'laka', 'li', 'maa', 'maahu', 'maaka', 'mai', 'min', 'minhu',
                'minka', 'minni', 'wa')
"""Not a complete set."""
NAMES_TO_FIX = {
    "mcdonald's": "McDonald's",
    'Arkit': 'ARKit',
    'Imessage': 'iMessage',
    'Ios': 'iOS',  # Not Cisco IOS
    'Itunes': 'iTunes',
    'LLVM': 'LLVM',
    'Macos': 'macOS',
    'Mapkit': 'MapKit',
    'Pdfkit': 'PDFKit',
    'S3RL': 'S3RL',
    'Sirikit': 'SiriKit',
    'Tvos': 'tvOS',
    'Watchos': 'watchOS',
    'Whats': "What's",
    'Wkwebview': 'WKWebView',
    'Wwdc': 'WWDC',
    'mcdonald': 'McDonald',
    'mcdonalds': "McDonald's",
}


class Mode(IntEnum):
    English = 1
    Japanese = 1 << 1
    Chinese = 1 << 2
    Arabic = 1 << 3


MODE_MAP = {
    Mode.Arabic: ARABIC_STOPS,
    Mode.Chinese: CHINESE_PARTICLES,
    Mode.English: STOP_WORDS,
    Mode.Japanese: JAPANESE_PARTICLES,
}


def get_name(word: str, names: dict[str, str] = NAMES_TO_FIX) -> str | None:
    word = word.lower()
    for name, output in names.items():
        if name.lower() == word:
            return output
    return None


def adjust_title(words: str,
                 modes: Iterable[Mode] = (Mode.English,),
                 names: dict[str, str] = NAMES_TO_FIX,
                 *,
                 disable_names: bool = False,
                 ampersands: bool = False) -> str:
    """
    Adjust a string that represents a title.
    
    Primarily for English to lowercase stop words, but also works for other languages. Some name
    rules are built-in but can also be passed in the ``names`` parameter.

    It is far from perfect.
    """
    original_words = words.strip().split()
    word_list = words.strip().title().split()
    name = get_name(word_list[0], names=names)
    if name is not None:
        title = [name]
    elif word_list[0].upper() == original_words[0]:
        title = [fix_apostrophes(original_words[0])]
    else:
        title = [fix_apostrophes(word_list[0])]
    if is_roman_numeral(title[0]):
        title = [title[0].upper()]
    last_index = len(original_words) - 1
    # MIX is a roman numeral but is more typically used in a sequence like 'Extended Mix', so do not
    # capitalise it
    ignore_roman = ('mix',)
    for mode in modes:
        to_lower_case_array = MODE_MAP[mode]
        index = 1
        for word in word_list[1:]:
            new_word = word
            if disable_names is False:
                name = get_name(new_word, names=names)
                if name is not None:
                    try:
                        title[index] = name
                    except IndexError:
                        title.append(name)
                    index += 1
                    continue
            # Detect an upper-case new_word not to change
            if original_words[index] == new_word.upper() and not re.match(r'[^\w]', new_word):
                # Detect I (not Roman numeral necessarily)
                if mode == Mode.English and new_word == 'I':
                    pass
                # ???
                elif index == last_index and re.match(r'[A-Z0-9]+', original_words[index]):
                    title.append(original_words[index])
                    continue
            begin = end = ''
            if re.match(r'^\W', new_word):
                begin = assert_not_none(re.match(r'^(\W+)', new_word)).groups()[0]
                new_word = new_word[1:]
            if re.match(r'\w+\W$', new_word):
                end = assert_not_none(re.match(r'\w+(\W+)$', new_word)).groups()[0]
                new_word = new_word[0:-1]
            if new_word.lower() in to_lower_case_array:
                new_word = word_list[index] = new_word.lower()
            new_word = fix_apostrophes(new_word)
            if is_roman_numeral(new_word) and new_word.lower() not in ignore_roman:
                new_word = new_word.upper()
            if mode == Mode.English and new_word.lower() in ENGLISH_ABBREV:
                end = ''
            ordinal_match = re.match(ENGLISH_ORDINAL_RE, new_word, flags=re.IGNORECASE)
            if mode == Mode.English and ordinal_match is not None:
                new_word = (ordinal_match.group(1) + ordinal_match.group(2).lower())
            new_word = f'{begin}{new_word}{end}'
            try:
                title[index] = new_word
            except IndexError:
                title.append(new_word)
            index += 1
    title_ = ' '.join(title)
    if ampersands:
        title_ = title_.replace(' and ', ' & ')
    return title_
