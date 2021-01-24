#!/usr/bin/env python3

# 3rd parties
import pytest

# forban
from forban.logs import LogEntry
from .utils import assert_responses_equal, dummy_prepared_request, dummy_response


def iter_pairs(client):
    for url in ('http://one/', 'http://two/'):
        for method, body in [('GET', None), ('POST', b'dummy body')]:
            for headers in ({}, {'X-Test': '1'}, {'X-Test': '2'}):
                # NB there's more comprehensive tests for cache key equivalent in `test_cache_keys.py`, but here's a sample
                request_kwargs = {'url': url, 'method': method, 'headers': headers, 'data': body}
                prepared_req = dummy_prepared_request(client, **request_kwargs)
                res = dummy_response(prepared_req)
                yield request_kwargs, res


def test_cache(reinstantiable_client):
    client = reinstantiable_client()
    pairs = [
        (dummy_prepared_request(client, **req), res)
        for req, res in iter_pairs(client)
    ]
    log_entries = [
        LogEntry(prepared_req)
        for prepared_req, _res_unused in pairs
    ]
    cache = client.cache
    for (prepared_req, _res_unused), log in zip(pairs, log_entries):
        assert cache.get(prepared_req, log) is None  # else test is invalid
        assert log.cached is False
    for prepared_req, res in pairs:
        cache.put(prepared_req, res)
    cache = reinstantiable_client().cache
    for (prepared_req, res), log in zip(pairs, log_entries):
        assert_responses_equal(cache.get(prepared_req, log), res)
        assert log.cached is True


@pytest.mark.usefixtures('mocked_sleep')
def test_client_caching(mocker, reinstantiable_client):
    client = reinstantiable_client()
    for req, res in iter_pairs(client):
        fetch = mocker.patch.object(client.session, 'request', return_value=res)
        assert_responses_equal(client.fetch(**req), res)
        fetch.assert_called_once()
    client = reinstantiable_client()
    for req, res in iter_pairs(client):
        fetch = mocker.patch.object(client.session, 'request', return_value=res)
        assert_responses_equal(client.fetch(**req), res)
        fetch.assert_not_called()


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
