class Picture:
    mime: str
    data: bytes
    type: int


class FLAC:
    def __init__(self, filename: str) -> None:
        ...

    def add_picture(self, picture: Picture) -> None:
        ...

    def save(self) -> None:
        ...
