#!/usr/bin/env python3

# forban
from .utils import dummy_response


def test_simple_store_and_retrieve(storage):
    key = 'somestring'
    assert storage.retrieve(key) is None
    storage.store(key, dummy_response())
    assert storage.retrieve(key).__getstate__() == dummy_response().__getstate__()
    assert storage.retrieve(key).content == dummy_response().content
    assert storage.retrieve(key).__getstate__() != dummy_response(status_code=401).__getstate__()
