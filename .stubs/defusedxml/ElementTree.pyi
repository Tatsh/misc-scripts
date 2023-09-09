from pathlib import Path
from typing import TextIO
from xml.etree import ElementTree

def parse(filepath: Path | str | TextIO) -> ElementTree.ElementTree:
    ...
