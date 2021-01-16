#!/usr/bin/env python3

# standards
from io import BytesIO
from itertools import combinations, product
from typing import Any, Dict, Optional

# 3rd parties
from requests import PreparedRequest, Response
from requests.structures import CaseInsensitiveDict


def dummy_prepared_request(
    method: str = 'POST',
    url: str = 'http://example.com/test',
    params: Optional[Dict[str, str]] = None,
    data: bytes = b'This is my request data',
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    json: Any = None,
):
    prepared_req = PreparedRequest()
    prepared_req.prepare(
        method,
        url,
        headers=headers,
        data=data,
        params=params,
        cookies=cookies,
        json=json,
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
    res.headers = CaseInsensitiveDict(headers or {})
    res.url = url
    res.raw = BytesIO(data)
    return res


def iter_nonequal_pairs(equivalencies):
    for index, group in enumerate(equivalencies):
        all_other_elems = [
            other_group[0]
            for other_index, other_group in enumerate(equivalencies)
            if other_index > index  # Using > to avoid wastefully comparing A to B and B to A
        ]
        for elem, other_elem in product(group, all_other_elems):
            yield elem, other_elem


def iter_equal_pairs(equivalencies):
    for group in equivalencies:
        if len(group) > 2:
            for elem_1, elem_2 in combinations(group, 2):
                yield elem_1, elem_2
