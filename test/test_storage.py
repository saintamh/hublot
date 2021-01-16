#!/usr/bin/env python3

# 3rd parties
import pytest

# forban
from .utils import dummy_response


def test_header_storage(header_storage):
    key = 'somestring'
    assert header_storage.select(key) is None
    res = dummy_response()
    res.content  # it's to to consume the data to memory, pylint: disable=pointless-statement
    res._content = None  # pylint: disable=protected-access
    header_storage.insert(key, res)
    retrieved = header_storage.select(key)
    assert retrieved.__getstate__() == res.__getstate__()


@pytest.mark.parametrize(
    'body',
    [
        b'',
        b'hello',
        b'hello' * 1000
    ],
)
def test_body_storage(body_storage, body):
    key = 'somestring'
    body_storage.write(key, body)
    assert body_storage.read(key) == body
