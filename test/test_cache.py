#!/usr/bin/env python3

# forban
from forban.logs import LogEntry
from .utils import assert_responses_equal, dummy_prequest, dummy_response


def iter_pairs(client):
    for url in ('http://one/', 'http://two/'):
        for method, body in [('GET', None), ('POST', b'dummy body')]:
            for headers in ({}, {'X-Test': '1'}, {'X-Test': '2'}):
                # NB there's more comprehensive tests for cache key equivalent in `test_cache_keys.py`, but here's a sample
                request_kwargs = {'url': url, 'method': method, 'headers': headers, 'data': body}
                preq = dummy_prequest(client, **request_kwargs)
                res = dummy_response(preq)
                yield request_kwargs, res


def test_cache(reinstantiable_client):
    client = reinstantiable_client()
    pairs = [
        (dummy_prequest(client, **req), res)
        for req, res in iter_pairs(client)
    ]
    log_entries = [
        LogEntry(preq)
        for preq, _res_unused in pairs
    ]
    cache = client.cache
    for (preq, _res_unused), log in zip(pairs, log_entries):
        assert cache.get(preq, log) is None  # else test is invalid
        assert log.cached is False
    for preq, res in pairs:
        cache.put(preq, res)
    cache = reinstantiable_client().cache
    for (preq, res), log in zip(pairs, log_entries):
        assert_responses_equal(cache.get(preq, log), res)
        assert log.cached is True


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


def test_http_errors_are_cached(client, server):
    one = client.get(f'{server}/fail-with-random-value', raise_for_status=False)
    assert one.status_code == 500
    two = client.get(f'{server}/fail-with-random-value', raise_for_status=False)
    assert two.status_code == 500
    three = client.get(f'{server}/fail-with-random-value', raise_for_status=False, force_cache_stale=True)
    assert three.status_code == 500
    assert one.text == two.text
    assert two.text != three.text
