#!/usr/bin/env python3

# melba
from melba.melba import LogEntry
from .utils import dummy_prepared_request, dummy_response


def test_simple_cache_use(cache):
    prepared_req = dummy_prepared_request()
    log = LogEntry(prepared_req)
    assert cache.get(prepared_req, log) is None
    assert log.cache_key is not None
    cache.put(prepared_req, dummy_response())
    assert cache.get(prepared_req, log).__getstate__() == dummy_response().__getstate__()
