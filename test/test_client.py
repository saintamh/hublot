#!/usr/bin/env python3

# standards
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

# 3rd parties
import pytest
import requests

# hublot
from hublot import Cache, HttpClient, HttpError, TooManyRedirects
from hublot.cache.storage import DiskStorage


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


def test_no_cache_by_default(server):
    client = HttpClient()
    one = client.get(f'{server}/unique-number').text
    two = client.get(f'{server}/unique-number').text
    assert one != two  # not cached


def test_null_cache(server):
    client = HttpClient(cache=None)
    one = client.get(f'{server}/unique-number').text
    two = client.get(f'{server}/unique-number').text
    assert one != two  # not cached


def test_cache_as_path(server):
    with TemporaryDirectory() as tmp:
        client = HttpClient(cache=Path(tmp))
        one = client.get(f'{server}/unique-number').text
        two = client.get(f'{server}/unique-number').text
    assert one == two  # cached


def test_cache_as_cache_object(server):
    with TemporaryDirectory() as tmp:
        client = HttpClient(cache=Cache(DiskStorage(Path(tmp))))
        one = client.get(f'{server}/unique-number').text
        two = client.get(f'{server}/unique-number').text
    assert one == two  # cached


def test_force_cache_stale(client, server):
    one = client.get(f'{server}/unique-number').text
    two = client.get(f'{server}/unique-number', force_cache_stale=True).text
    three = client.get(f'{server}/unique-number').text
    assert one != two  # cache not read on 2nd call
    assert two == three  # but cache was written on 2nd call


def test_courtesy_sleep_by_default(mocked_courtesy_sleep, server):
    client = HttpClient()
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_courtesy_sleep.assert_called_once()
    delay, = mocked_courtesy_sleep.call_args[0]
    assert delay > 1


def test_null_courtesy_sleep(mocked_courtesy_sleep, server):
    client = HttpClient(courtesy_sleep=None)
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_courtesy_sleep.assert_not_called()


def test_custom_courtesy_sleep(mocked_courtesy_sleep, server):
    client = HttpClient(courtesy_sleep=timedelta(minutes=2))
    client.get(f'{server}/unique-number')
    client.get(f'{server}/unique-number')
    mocked_courtesy_sleep.assert_called_once()
    delay, = mocked_courtesy_sleep.call_args[0]
    assert delay == pytest.approx(120, 0.1)


def test_http_errors_are_raised(client, server):
    with pytest.raises(HttpError):
        client.get(f'{server}/fail-with-random-value')


def test_auto_raise_can_be_disabled(client, server):
    res = client.get(f'{server}/fail-with-random-value', raise_for_status=False)
    assert res.status_code == 500


def test_redirect(client, server):
    res = client.get(f'{server}/redirect/chain/1')
    assert res.status_code == 200
    assert res.text == 'Landed'


def test_no_redirect(client, server):
    res = client.get(f'{server}/redirect/chain/1', allow_redirects=False)
    assert res.status_code == 302
    assert res.text == 'Bounce 1'


def test_redirect_response_bodies(cache, server):
    for _ in (1, 2):
        client = HttpClient(cache=cache)
        res = client.get(f'{server}/redirect/chain/1')
        assert res.status_code == 200
        assert res.text == 'Landed'


def test_redirects_set_response_history(cache, server):
    for _ in (1, 2):
        client = HttpClient(cache=cache)
        res = client.get(f'{server}/redirect/chain/1')
        assert [r.text for r in res.history] == ['Bounce 1', 'Bounce 2']


def test_redirect_loop(client, server):
    # Make sure that the caching doesn't interfere with Requests' ability to detect redirect loops
    with pytest.raises(TooManyRedirects):
        client.fetch(f'{server}/redirect/loop')


def test_client_preserves_casing_of_percent_escapes_in_path(client, server):
    ref_upper = client.get(f'{server}/bicam%C3%A9ral').text
    assert ref_upper.startswith('upper')
    ref_lower = client.get(f'{server}/bicam%c3%a9ral').text
    assert ref_lower.startswith('lower')
    assert client.get(f'{server}/bicam%C3%A9ral').text == ref_upper
    assert client.get(f'{server}/bicam%c3%a9ral').text == ref_lower


def test_client_preserves_casing_of_percent_escapes_in_query(client, server):
    ref_upper = client.get(f'{server}/bicam%C3%A9ral?name=Zo%C3%A9').text
    assert ref_upper.startswith('upper')
    ref_lower = client.get(f'{server}/bicam%C3%A9ral?name=Zo%c3%a9').text
    assert ref_lower.startswith('lower')
    assert client.get(f'{server}/bicam%C3%A9ral?name=Zo%C3%A9').text == ref_upper
    assert client.get(f'{server}/bicam%C3%A9ral?name=Zo%c3%a9').text == ref_lower


def test_client_can_fetch_from_server_that_redirects_based_on_escape_code_case(client, server):
    url = f'{server}/redirig%C3%A9'
    with pytest.raises(requests.TooManyRedirects):
        requests.get(url, timeout=60)  # doesn't work with `requests`, boo
    assert client.get(url).text == 'lower'  # Hublot can get around it though, hurray
