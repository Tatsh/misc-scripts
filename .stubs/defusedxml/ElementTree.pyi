from pathlib import Path
from typing import TextIO
from xml.etree import ElementTree as ET

def parse(filepath: Path | str | TextIO) -> ET.ElementTree:
    ...
