from __future__ import annotations

from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

__all__ = ('chunks',)


@overload
def chunks(seq: str, n: int) -> Iterator[str]:
    pass


@overload
def chunks(seq: Sequence[str], n: int) -> Iterator[Sequence[str]]:
    pass


def chunks(seq: Sequence[str] | str, n: int) -> Iterator[Sequence[str] | str]:
    """Iterate a sequence in chunks."""
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
