#!/usr/bin/env python3

# 3rd parties
import pytest

# hublot
from hublot import HttpClient, Request


@pytest.mark.parametrize(
    ['request_kwargs', 'expected_payload'],
    [

        pytest.param(
            dict(params={'a': 'b'}),
            {
                'method': 'GET',
                'headers': {},
                'args': {'a': 'b'},
                'data': '',
            },
            id='simple get',
        ),

        pytest.param(
            dict(data={'a': 'b'}),
            {
                'method': 'POST',
                'headers': {'Content-Length': '3', 'Content-Type': 'application/x-www-form-urlencoded'},
                'args': {},
                'data': 'a=b',
            },
            id='simple post',
        ),

        pytest.param(
            dict(json={'a': 'b'}),
            {
                'method': 'POST',
                'headers': {'Content-Length': '9', 'Content-Type': 'application/json'},
                'args': {},
                'data': '{"a":"b"}',
            },
            id='simple JSON post',
        ),

        pytest.param(
            dict(method='SLURP'),
            {
                'method': 'SLURP',
                'headers': {'Content-Length': '0'},
                'args': {},
                'data': '',
            },
            id='custom method, no body',
        ),

        pytest.param(
            dict(method='POST', data=b'\x00\x01\x02'),
            {
                'method': 'POST',
                'headers': {'Content-Length': '3', 'Content-Type': 'application/x-www-form-urlencoded'},
                'args': {},
                'data': r'\x00\x01\x02',
            },
            id='post unprintable bytes',
        ),

        pytest.param(
            dict(method='POST', data=b'\x00\x01\x02', headers={'Content-Type': 'application/whatever'}),
            {
                'method': 'POST',
                'headers': {'Content-Length': '3', 'Content-Type': 'application/whatever'},
                'args': {},
                'data': r'\x00\x01\x02',
            },
            id='post with custom content-type',
        ),

    ]
)
def test_http_requests(engines, server, request_kwargs, expected_payload) -> None:
    client = HttpClient(engines=engines)
    res = client.fetch(Request(f'{server}/echo', **request_kwargs))
    payload = res.json()
    print(payload)
    assert isinstance(payload, dict)
    for key in ['Accept', 'Accept-Encoding', 'Host', 'User-Agent']:
        payload['headers'].pop(key, None)
    assert payload == expected_payload


def test_long_response(engines, server) -> None:
    client = HttpClient(engines=engines)
    length = 12*1024*1024
    res = client.fetch(f'{server}/bytes', params={'length': length})
    assert res.content == b'\x00' * length
