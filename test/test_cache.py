#!/usr/bin/env python3

# standards
from collections import OrderedDict
from copy import deepcopy
from itertools import combinations

# 3rd parties
import pytest

# melba
from melba.melba import Cache, LogEntry
from .utils import dummy_prepared_request, dummy_response


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


def iter_unique_tests():
    seen = {}
    for group in EQUIVALENCIES:
        key = None
        for config in group:
            key = Cache.compute_key(dummy_prepared_request(**config))
            yield config, key, deepcopy(seen)
        seen[key] = config


@pytest.mark.parametrize(
    'config, key, seen',
    iter_unique_tests(),
)
def test_unique(config, key, seen):
    assert key not in seen, (config, seen[key])


def iter_equivalency_tests():
    for group in EQUIVALENCIES:
        if len(group) > 2:
            for config_1, config_2 in combinations(group, 2):
                yield config_1, config_2


@pytest.mark.parametrize(
    'config_1, config_2',
    iter_equivalency_tests(),
)
def test_equivalency(config_1, config_2):
    key_1 = Cache.compute_key(dummy_prepared_request(**config_1))
    key_2 = Cache.compute_key(dummy_prepared_request(**config_2))
    assert key_1 == key_2, (config_1, config_2)
