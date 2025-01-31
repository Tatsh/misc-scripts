from tatsh_misc_utils.itertools import chunks


def test_chunks_string() -> None:
    result = list(chunks('abcdefgh', 3))
    assert result == ['abc', 'def', 'gh']


def test_chunks_list() -> None:
    result = list(chunks(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], 3))
    assert result == [['a', 'b', 'c'], ['d', 'e', 'f'], ['g', 'h']]


def test_chunks_empty_string() -> None:
    result = list(chunks('', 3))
    assert result == []


def test_chunks_empty_list() -> None:
    result = list(chunks([], 3))
    assert result == []


def test_chunks_single_element_string() -> None:
    result = list(chunks('a', 3))
    assert result == ['a']


def test_chunks_single_element_list() -> None:
    result = list(chunks(['a'], 3))
    assert result == [['a']]


def test_chunks_n_greater_than_length_string() -> None:
    result = list(chunks('abc', 5))
    assert result == ['abc']


def test_chunks_n_greater_than_length_list() -> None:
    result = list(chunks(['a', 'b', 'c'], 5))
    assert result == [['a', 'b', 'c']]
