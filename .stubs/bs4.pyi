from typing import Iterable, List, Mapping, Union


class Tag:
    attrs: Mapping[str, str]
    contents: Iterable[str]

    def select(self, selector: str) -> Iterable[Tag]:
        ...

    def __getitem__(self, key: str) -> str:
        ...


class BeautifulSoup:
    body: Tag

    def __init__(self, root: Union[str, bytes], parser: str) -> None:
        ...

    def select(self, selector: str) -> List[Tag]:
        ...
