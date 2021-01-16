#!/usr/bin/env python3

# standards
from pathlib import Path
from tempfile import TemporaryDirectory

# 3rd parties
import pytest

# forban
from forban import Cache, Client


@pytest.mark.parametrize(
    'kwargs, expected_method',
    [
        ({}, 'GET'),
        ({'data': None}, 'GET'),
        ({'data': b''}, 'POST'),
        ({'data': b'a=b'}, 'POST'),
        ({'data': {'a': 'b'}}, 'POST'),
        ({'json': None}, 'GET'),
        ({'json': ''}, 'POST'),
        ({'json': {'a': 'b'}}, 'POST'),
    ]
)
def test_default_method(client, server, kwargs, expected_method):
    assert client.fetch(f'{server}/method-test', **kwargs).text == expected_method


@pytest.mark.usefixtures('mocked_sleep')
def test_no_cache_by_default(server):
    client = Client()
    one = client.get(f'{server}/unique-number').text
    two = client.get(f'{server}/unique-number').text
    assert one != two  # not cached


@pytest.mark.usefixtures('mocked_sleep')
def test_null_cache(server):
    client = Client(cache=None)
    one = client.get(f'{server}/unique-number').text
    two = client.get(f'{server}/unique-number').text
    assert one != two  # not cached


@pytest.mark.usefixtures('mocked_sleep')
def test_cache_as_path(server):
    with TemporaryDirectory() as tmp:
        client = Client(cache=Path(tmp))
        one = client.get(f'{server}/unique-number').text
        two = client.get(f'{server}/unique-number').text
    assert one == two  # cached


@pytest.mark.usefixtures('mocked_sleep')
def test_cache_as_cache_object(server):
    with TemporaryDirectory() as tmp:
        client = Client(cache=Cache(Path(tmp)))
        one = client.get(f'{server}/unique-number').text
        two = client.get(f'{server}/unique-number').text
    assert one == two  # cached
