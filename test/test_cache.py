#!/usr/bin/env python3

# forban
from forban.logs import LogEntry
from .utils import dummy_prepared_request, dummy_response


def test_cache(cache):
    prepared_req = dummy_prepared_request()
    response = dummy_response()
    log = LogEntry(prepared_req)
    assert cache.get(prepared_req, log) is None  # else test is invalid
    assert log.cached is False
    cache.put(prepared_req, response)
    assert cache.get(prepared_req, log).__getstate__() == response.__getstate__()
    assert log.cached is True


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
