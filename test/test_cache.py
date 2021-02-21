#!/usr/bin/env python3

# forban
from forban.logs import LogEntry
from .utils import assert_responses_equal, dummy_prepared_request, dummy_response


def iter_pairs(client):
    for url in ('http://one/', 'http://two/'):
        for method, body in [('GET', None), ('POST', b'dummy body')]:
            for headers in ({}, {'X-Test': '1'}, {'X-Test': '2'}):
                # NB there's more comprehensive tests for cache key equivalent in `test_cache_keys.py`, but here's a sample
                request_kwargs = {'url': url, 'method': method, 'headers': headers, 'data': body}
                preq = dummy_prepared_request(client, **request_kwargs)
                res = dummy_response(preq)
                yield request_kwargs, res


def test_cache(reinstantiable_client):
    client = reinstantiable_client()
    pairs = [
        (dummy_prepared_request(client, **req), res)
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
    for (preq, res), log in zip(pairs, log_entries):
        cache.put(preq, log, res)
    cache = reinstantiable_client().cache
    for (preq, res), log in zip(pairs, log_entries):
        assert_responses_equal(cache.get(preq, log), res)
        assert log.cached is True


def test_client_caching(mocker, reinstantiable_client):
    client = reinstantiable_client()
    for req, res in iter_pairs(client):
        request = mocker.patch.object(client.session, 'request', return_value=res)
        assert_responses_equal(client.fetch(**req), res)
        request.assert_called_once()
    client = reinstantiable_client()
    for req, res in iter_pairs(client):
        request = mocker.patch.object(client.session, 'request', return_value=res)
        assert_responses_equal(client.fetch(**req), res)
        request.assert_not_called()


def test_http_errors_are_cached(client, server):
    one = client.get(f'{server}/fail-with-random-value', raise_for_status=False)
    assert one.status_code == 500
    two = client.get(f'{server}/fail-with-random-value', raise_for_status=False)
    assert two.status_code == 500
    three = client.get(f'{server}/fail-with-random-value', raise_for_status=False, force_cache_stale=True)
    assert three.status_code == 500
    assert one.text == two.text
    assert two.text != three.text


def test_repeated_http_headers_are_cached(reinstantiable_client, server):
    client = reinstantiable_client()
    res = client.get(f'{server}/cookies/set-two-cookies')
    assert res.headers.get('Set-Cookie') == 'a=1, b=2'
    assert res.raw._fp.headers.get_all('Set-Cookie') == ['a=1', 'b=2']   # pylint: disable=protected-access
    unique = res.text

    client = reinstantiable_client()
    res = client.get(f'{server}/cookies/set-two-cookies')
    assert res.text == unique  # check that it was cached
    assert res.headers.get('Set-Cookie') == 'a=1, b=2'
    #if callable(getattr(res.headers, 'get_all', None)):
    assert res.headers.get_all('Set-Cookie') == ['a=1', 'b=2']

    assert [f'{c.name}={c.value!r}' for c in client.session.cookies] == ["a='1'", "b='2'"]
