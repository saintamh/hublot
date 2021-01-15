#!/usr/bin/env python3

# forban
from .utils import dummy_response


def test_header_storage(header_storage):
    key = 'somestring'
    assert header_storage.select(key) is None
    res = dummy_response()
    res._content = None  # pylint: disable=protected-access
    header_storage.insert(key, res)
    retrieved = header_storage.select(key)
    assert retrieved.__getstate__() == res.__getstate__()
