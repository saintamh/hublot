#!/usr/bin/env python3

# standards
from collections import OrderedDict

# 3rd parties
import pytest

# forban
from forban.forban import Cache, LogEntry
from .utils import dummy_prepared_request, dummy_response, iter_equal_pairs, iter_nonequal_pairs


def test_simple_cache_use(cache):
    prepared_req = dummy_prepared_request()
    log = LogEntry(prepared_req)
    assert cache.get(prepared_req, log) is None
    assert log.cache_key is not None
    cache.put(prepared_req, dummy_response())
    assert cache.get(prepared_req, log).__getstate__() == dummy_response().__getstate__()


EQUIVALENCIES = [
    # For every attribute of a PreparedRequest, lists groups values such that values within the same group should be cached under
    # the same key, but not across groups

    # Obviously requests using different methods should be cached separately
    [{'method': 'GET'}],
    [{'method': 'POST'}],

    # URLs are case sensitive
    [{'url': 'http://cache-test/url'}],
    [{'url': 'http://cache-test/URL'}],
    [{'url': 'http://cache-test/URL/'}],

    # The ordering of the parameters in the URL string matters. They're not parsed at all, so a final '&' is also a cache breaker
    [{'url': 'http://cache-test/TEST?a=1&b=2'}],
    [{'url': 'http://cache-test/TEST?b=2&a=1'}],
    [{'url': 'http://cache-test/TEST?a=1&b=2&'}],

    # `params` are also part of the URL key
    [{'url': 'http://cache-test/params', 'params': {}}],
    [{'url': 'http://cache-test/params', 'params': {'x': 'a'}}],

    # `params` get appended to the URL, so these are equivalent. Using OrderedDict for pythons before 3.7.
    [
        {'url': 'http://cache-test/params-test', 'params': OrderedDict([('a', '1'), ('b', '2')])},
        {'url': 'http://cache-test/params-test?', 'params': OrderedDict([('a', '1'), ('b', '2')])},
        {'url': 'http://cache-test/params-test?a=1', 'params': OrderedDict([('b', '2')])},
        {'url': 'http://cache-test/params-test?a=1&b=2', 'params': OrderedDict()},
    ],

    # The presence, absence, or value of a header are all enough to bust the cache
    [{'url': 'http://cache-test/header-test', 'headers': {}}],
    [{'url': 'http://cache-test/header-test', 'headers': {'X-Test': '1'}}],
    [{'url': 'http://cache-test/header-test', 'headers': {'X-Test': '2'}}],

    # The `requests` library will normalise the case of headers before sending them off to the server, and so headers are
    # case-insensitive, and so all of these get the same cache key
    [
        {'url': 'http://cache-test/header-test-2', 'headers': {'X-Test': '1'}},
        {'url': 'http://cache-test/header-test-2', 'headers': {'x-test': '1'}},
        {'url': 'http://cache-test/header-test-2', 'headers': {'X-TEST': '1'}},
    ],

    # Setting a cookie via `cookies` is the same as setting it manually in a header
    [
        {'url': 'http://cache-test/cookie-test', 'cookies': {'a': '1'}, 'headers': {}},
        {'url': 'http://cache-test/cookie-test', 'cookies': {}, 'headers': {'Cookie': 'a=1'}},
    ],

    # Setting `data` as a dict is equivalent to setting it manually as bytes
    [
        {'url': 'http://cache-test/data-test', 'data': {'a': '1'}},
        {
            'url': 'http://cache-test/data-test',
            'data': 'a=1',
            'headers': {'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': '3'},
        },
    ],

    # Setting `json` is equivalent to manually building the request
    [
        {'url': 'http://cache-test/data-test', 'json': {'a': '1'}},
        {
            'url': 'http://cache-test/data-test',
            'data': '{"a": "1"}',
            'headers': {'Content-Type': 'application/json', 'Content-Length': '10'},
        },
    ],
]


@pytest.mark.parametrize(
    'config_1, config_2',
    iter_nonequal_pairs(EQUIVALENCIES),
)
def test_unique_keys(config_1, config_2):
    key = Cache.compute_key(dummy_prepared_request(**config_1))
    other_key = Cache.compute_key(dummy_prepared_request(**config_2))
    assert key != other_key


@pytest.mark.parametrize(
    'config_1, config_2',
    iter_nonequal_pairs(EQUIVALENCIES),
)
def test_unique_requests(cache, config_1, config_2):
    prepared_req_1 = dummy_prepared_request(**config_1)
    prepared_req_2 = dummy_prepared_request(**config_2)
    cache.put(prepared_req_1, dummy_response())
    assert cache.get(prepared_req_2, LogEntry(prepared_req_2)) is None


@pytest.mark.parametrize(
    'config_1, config_2',
    iter_equal_pairs(EQUIVALENCIES),
)
def test_equivalent_keys(config_1, config_2):
    key_1 = Cache.compute_key(dummy_prepared_request(**config_1))
    key_2 = Cache.compute_key(dummy_prepared_request(**config_2))
    assert key_1 == key_2, (config_1, config_2)


@pytest.mark.parametrize(
    'config_1, config_2',
    iter_equal_pairs(EQUIVALENCIES),
)
def test_equivalent_requests(cache, config_1, config_2):
    prepared_req_1 = dummy_prepared_request(**config_1)
    prepared_req_2 = dummy_prepared_request(**config_2)
    response = dummy_response()
    assert cache.get(prepared_req_2, LogEntry(prepared_req_2)) is None  # else test is invalid
    cache.put(prepared_req_1, response)
    assert cache.get(prepared_req_2, LogEntry(prepared_req_2)).__getstate__() == response.__getstate__()


def test_cache_updates_log_entry_attributes(cache):
    prepared_req = dummy_prepared_request()
    log = LogEntry(prepared_req)
    assert log.cache_key is None
    assert log.cached is None
    cache.get(prepared_req, log)
    assert log.cache_key is not None
    assert log.cached is False
    cache.put(prepared_req, dummy_response())
    cache.get(prepared_req, log)
    assert log.cached is True
