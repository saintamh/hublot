#!/usr/bin/env python3

# standards
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

# 3rd parties
import pytest
from requests import HTTPError

# forban
from forban import Client, CourtesySleep, DiskCache


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
        client = Client(cache=DiskCache(Path(tmp)))
        one = client.get(f'{server}/unique-number').text
        two = client.get(f'{server}/unique-number').text
    assert one == two  # cached


@pytest.mark.usefixtures('mocked_sleep')
def test_force_cache_stale(server):
    with TemporaryDirectory() as tmp:
        client = Client(cache=DiskCache(Path(tmp)))
        one = client.get(f'{server}/unique-number').text
        two = client.get(f'{server}/unique-number', force_cache_stale=True).text
        three = client.get(f'{server}/unique-number').text
    assert one != two  # cache not read on 2nd call
    assert two == three  # but cache was written on 2nd call


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


def test_post_data(client, server):
    res = client.post(f'{server}/echo', data={'a': 'b'})
    assert res.json() == {'args': {}, 'files': {}, 'form': {'a':'b'}, 'json': None}


def test_post_open_file(client, server):
    dummy_file = Path(__file__)
    res = client.post(f'{server}/echo', data={'a': dummy_file.open('rb')})
    assert res.json() == {
        'args': {},
        'files': {},
        'form': {'a': dummy_file.read_text('UTF-8')},
        'json': None,
    }


def test_post_files(client, server):
    dummy_file = Path(__file__)
    res = client.post(f'{server}/echo', files={'f': dummy_file.open('rb')})
    assert res.json() == {
        'args': {},
        'files': {'f': dummy_file.read_text('UTF-8')},
        'form': {},
        'json': None,
    }


def test_post_json(client, server):
    res = client.post(f'{server}/echo', json={'a': 'b'})
    assert res.json() == {'args': {}, 'files': {}, 'form': {}, 'json': {'a': 'b'}}


def test_http_errors_are_raised(client, server):
    with pytest.raises(HTTPError):
        client.get(f'{server}/fail-with-random-value')


def test_redirect(client, server):
    res = client.get(f'{server}/redirect/chain/1')
    assert res.status_code == 200
    assert res.text == 'Landed'


def test_no_redirect(client, server):
    res = client.get(f'{server}/redirect/chain/1', allow_redirects=False)
    assert res.status_code == 302
    assert res.text == 'Bounce 1'


@pytest.mark.usefixtures('mocked_sleep')
def test_redirect_response_bodies(cache, server):
    for _ in (1, 2):
        client = Client(cache=cache)
        res = client.get(f'{server}/redirect/chain/1')
        assert res.status_code == 200
        assert res.text == 'Landed'
        assert [r.text for r in res.history] == ['Bounce 1', 'Bounce 2']
