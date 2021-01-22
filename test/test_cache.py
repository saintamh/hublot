#!/usr/bin/env python3

# 3rd parties
import pytest

# forban
from forban.logs import LogEntry
from .utils import dummy_prepared_request, dummy_response


PAIRS = [
    # NB there's more comprehensive tests for cache key equivalent in `test_cache_keys.py`, but here's a sample
    (
        {'url': url, 'method': method, 'headers': headers},
        dummy_response(),
    )
    for url in ('http://one/', 'http://two/')
    for method in ('GET', 'POST')
    for headers in ({}, {'X-Test': '1'}, {'X-Test': '2'})
]


def test_cache(reinstantiable_cache):
    pairs = [
        (dummy_prepared_request(**req), res)
        for req, res in PAIRS
    ]
    log_entries = [
        LogEntry(prepared_req)
        for prepared_req, _res_unused in pairs
    ]
    cache = reinstantiable_cache()
    for (prepared_req, _res_unused), log in zip(pairs, log_entries):
        assert cache.get(prepared_req, log) is None  # else test is invalid
        assert log.cached is False
    for prepared_req, res in pairs:
        cache.put(prepared_req, res)
    cache = reinstantiable_cache()
    for (prepared_req, res), log in zip(pairs, log_entries):
        assert cache.get(prepared_req, log).__getstate__() == res.__getstate__()
        assert log.cached is True


@pytest.mark.usefixtures('mocked_sleep')
def test_client_caching(mocker, reinstantiable_client):
    client = reinstantiable_client()
    for req, res in PAIRS:
        fetch = mocker.patch.object(client.session, 'request', return_value=res)
        assert client.fetch(**req).__getstate__() == res.__getstate__()
        fetch.assert_called_once()
    client = reinstantiable_client()
    for req, res in PAIRS:
        fetch = mocker.patch.object(client.session, 'request', return_value=res)
        assert client.fetch(**req).__getstate__() == res.__getstate__()
        fetch.assert_not_called()


def test_deleting_body_file_invalidates_cache(cache):
    prepared_req = dummy_prepared_request()
    response = dummy_response()
    log = LogEntry(prepared_req)

    # cache is empty
    assert cache.get(prepared_req, log) is None
    assert not list(cache.root_path.glob('*/*'))
    assert cache.headers.count() == 0

    # add one request
    cache.put(prepared_req, response)
    assert cache.get(prepared_req, log).__getstate__() == response.__getstate__()
    assert cache.headers.count() == 1

    # delete the file, cache is empty -- the req has gotten removed from the HeaderStorage as well
    body_file, = cache.root_path.glob('*/*')
    body_file.unlink()
    assert cache.get(prepared_req, log) is None  # no error, it's just gone
    assert cache.headers.count() == 0


@pytest.mark.usefixtures('mocked_sleep')
def test_http_errors_are_cached(client, server):
    one = client.get(f'{server}/fail-with-random-value', raise_for_status=False)
    assert one.status_code == 500
    two = client.get(f'{server}/fail-with-random-value', raise_for_status=False)
    assert two.status_code == 500
    three = client.get(f'{server}/fail-with-random-value', raise_for_status=False, force_cache_stale=True)
    assert three.status_code == 500
    assert one.text == two.text
    assert two.text != three.text
