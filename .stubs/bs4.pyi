from typing import Iterable


class Tag:
    contents: Iterable[str]

    def select(self, selector: str) -> Iterable[Tag]:
        ...

    def __getitem__(self, key: str) -> str:
        ...


class BeautifulSoup:
    body: Tag

    def __init__(self, root: str, parser: str) -> None:
        ...
