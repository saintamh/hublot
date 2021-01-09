#!/usr/bin/env python3

# standards
from io import BytesIO
from typing import Dict, Optional

# 3rd parties
from requests import Response


def dummy_response(
    status_code: int = 200,
    reason: str = 'OK',
    headers: Optional[Dict[str, str]] = None,
    url: str = 'http://example.com/example',
    data: bytes = b'This is my response data',
):
    res = Response()
    res.status_code = status_code
    res.reason = reason
    res.headers = headers or {}
    res.url = url
    res.raw = BytesIO(data)
    return res


def test_simple_store_and_retrieve(storage):
    key = 'somestring'
    assert storage.retrieve(key) is None
    storage.store(key, dummy_response())
    assert storage.retrieve(key).__getstate__() == dummy_response().__getstate__()
    assert storage.retrieve(key).content == dummy_response().content
    assert storage.retrieve(key).__getstate__() != dummy_response(status_code=401).__getstate__()
