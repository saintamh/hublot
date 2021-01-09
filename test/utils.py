#!/usr/bin/env python3

# standards
from io import BytesIO
from typing import Dict, Optional

# 3rd parties
from requests import PreparedRequest, Response


def dummy_prepared_request(
    method: str = 'POST',
    url: str = 'http://example.com/test',
    params: Optional[Dict[str, str]] = None,
    data: bytes = b'This is my request data',
    headers: Optional[Dict[str, str]] = None,
):
    prepared_req = PreparedRequest()
    prepared_req.prepare(
        method,
        url,
        headers=headers or {},
        data=data,
        params=params or {},
    )
    return prepared_req


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
