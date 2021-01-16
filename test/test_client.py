#!/usr/bin/env python3

# standards
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

# 3rd parties
import pytest

# forban
from forban import Cache, Client, CourtesySleep


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


def test_courtesy_sleep_by_default(mocked_sleep, server):
    client = Client()
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_sleep.assert_called_once()
    delay, = mocked_sleep.call_args[0]
    assert delay > 1


def test_null_courtesy_sleep(mocked_sleep, server):
    client = Client(courtesy_sleep=None)
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_sleep.assert_not_called()


def test_courtesy_sleep_as_int(mocked_sleep, server):
    client = Client(courtesy_sleep=78)
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_sleep.assert_called_once()
    delay, = mocked_sleep.call_args[0]
    assert delay == pytest.approx(78, 0.1)


def test_courtesy_sleep_as_timedelta(mocked_sleep, server):
    client = Client(courtesy_sleep=timedelta(minutes=2))
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_sleep.assert_called_once()
    delay, = mocked_sleep.call_args[0]
    assert delay == pytest.approx(120, 0.1)


def test_courtesy_sleep_as_object(mocked_sleep, server):
    client = Client(courtesy_sleep=CourtesySleep(78))
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_sleep.assert_called_once()
    delay, = mocked_sleep.call_args[0]
    assert delay == pytest.approx(78, 0.1)
