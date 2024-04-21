#!/usr/bin/env python3

# standards
from itertools import combinations, product
from typing import Dict, Optional

# hublot
from hublot import HttpClient, Request, Response
from hublot.compile import compile_request
from hublot.datastructures import CompiledRequest, Headers


def dummy_compiled_request(client: HttpClient, **kwargs) -> CompiledRequest:
    url = kwargs.pop("url", "http://example.com/test")
    if isinstance(url, str):
        kwargs.setdefault("method", "POST")
        if kwargs["method"] in ("POST", "PUT") and "json" not in kwargs:
            kwargs.setdefault("data", b"This is my request data")
        request = Request(url=url, **kwargs)
    else:
        request = url
    return compile_request(
        request,
        client.config,
        client.cookies,
        num_retries=0,
    )


def dummy_response(
    creq: CompiledRequest,
    from_cache: bool = False,
    status_code: int = 200,
    reason: str = "OK",
    headers: Optional[Dict[str, str]] = None,
    data: bytes = b"This is my response data",
) -> Response:
    return Response(
        request=creq,
        from_cache=from_cache,
        history=[],
        status_code=status_code,
        reason=reason,
        headers=Headers(headers),
        content=data,
    )


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
