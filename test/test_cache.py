#!/usr/bin/env python3

# standards
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Tuple

# 3rd parties
import pytest

# hublot
from hublot import HttpClient, Response
from hublot.cache.storage import DiskStorage
from hublot.logs import LogEntry
from .utils import dummy_compiled_request, dummy_response


def iter_pairs(client: HttpClient) -> Iterable[Tuple[dict, Response]]:
    for url in ("http://one/", "http://two/"):
        for method, body in [("GET", None), ("POST", b"dummy body")]:
            for headers in ({}, {"X-Test": "1"}, {"X-Test": "2"}):
                # NB there's more comprehensive tests for cache key equivalent in `test_cache_keys.py`, but here's a sample
                request_kwargs = {"url": url, "method": method, "headers": headers, "data": body}
                creq = dummy_compiled_request(client, **request_kwargs)
                res = dummy_response(creq, from_cache=True)
                yield request_kwargs, res


def test_cache(reinstantiable_client) -> None:
    client = reinstantiable_client()
    pairs = [(dummy_compiled_request(client, **req), res) for req, res in iter_pairs(client)]
    log_entries = [LogEntry(creq) for creq, _res_unused in pairs]
    cache = client.cache
    for (creq, _res_unused), log in zip(pairs, log_entries):
        assert cache.get(creq, log) is None  # else test is invalid
        assert log.cached is False
    for (creq, res), log in zip(pairs, log_entries):
        cache.put(creq, log, res)
    cache = reinstantiable_client().cache
    for (creq, res), log in zip(pairs, log_entries):
        assert cache.get(creq, log) == res
        assert log.cached is True


def test_client_caching(mocker, reinstantiable_client) -> None:
    client = reinstantiable_client()
    for req, res in iter_pairs(client):
        res = replace(res, from_cache=False)
        request = mocker.patch.object(client.engine, "request", return_value=res)
        assert client.fetch(**req) == res
        request.assert_called_once()
    client = reinstantiable_client()
    for req, res in iter_pairs(client):
        res = replace(res, from_cache=True)
        request = mocker.patch.object(client.engine, "request", return_value=res)
        assert client.fetch(**req) == res
        request.assert_not_called()


def test_http_errors_are_cached(client, server) -> None:
    one = client.get(f"{server}/fail-with-random-value", raise_for_status=False)
    assert one.status_code == 500
    two = client.get(f"{server}/fail-with-random-value", raise_for_status=False)
    assert two.status_code == 500
    three = client.get(f"{server}/fail-with-random-value", raise_for_status=False, force_cache_stale=True)
    assert three.status_code == 500
    assert one.text == two.text
    assert two.text != three.text


def test_repeated_http_headers_are_cached(reinstantiable_client, server) -> None:
    client = reinstantiable_client()
    res = client.get(f"{server}/cookies/set-two-cookies")
    assert res.headers.get("Set-Cookie") == "a=1; b=2"
    assert sorted(f"{c.name}={c.value!r}" for c in client.cookies) == ["a='1'", "b='2'"]
    unique = res.text

    client = reinstantiable_client()
    res = client.get(f"{server}/cookies/set-two-cookies")
    assert res.text == unique  # it was cached
    assert res.headers.get("Set-Cookie") == "a=1; b=2"
    assert res.headers.get_all("Set-Cookie") == ["a=1", "b=2"]

    assert sorted(f"{c.name}={c.value!r}" for c in client.cookies) == ["a='1'", "b='2'"]
    assert [f"{c.name}={c.value!r}" for c in client.cookies] == ["a='1'", "b='2'"]


def test_cache_wont_save_body_with_wrong_length(client) -> None:
    creq = dummy_compiled_request(
        client,
        data=b"More than one byte",
        headers={"Content-Length": "1"},
    )
    response = dummy_response(creq)
    with pytest.raises(Exception) as ex:
        client.cache.put(creq, LogEntry(creq), response)
    assert "body has 18 bytes but Content-Length is 1" in str(ex)


def test_cache_wont_save_get_request_with_content_length(client) -> None:
    creq = dummy_compiled_request(
        client,
        method="GET",
    )
    creq.headers["Content-Length"] = "999"
    response = dummy_response(creq)
    with pytest.raises(Exception) as ex:
        client.cache.put(creq, LogEntry(creq), response)
    assert "body has 0 bytes but Content-Length is 999" in str(ex)


def test_cache_can_handle_empty_post_request(client, server) -> None:
    for _from_cache_unused in (False, True):
        res = client.fetch(f"{server}/echo", data={})
        obtained = res.json()
        obtained.pop("headers")
        assert obtained == {"method": "POST", "args": {}, "data": ""}


def test_cache_can_be_specified_as_path() -> None:
    client = HttpClient(cache=Path("/cache"))
    assert client.cache is not None
    assert isinstance(client.cache.storage, DiskStorage)
    assert client.cache.storage.root_path == Path("/cache")


def test_cache_cannot_be_specified_as_str() -> None:
    # The idea of not accepting strings is mostly to just keep the client code readable, and maybe preserve forward flexibility.
    # But if this ever a problem, we could consider auto-converting str objects to Path objects.
    with pytest.raises(TypeError):
        HttpClient(cache="/cache")


def test_from_cache_attribute(client, server) -> None:
    for from_cache in (False, True):
        res = client.fetch(f"{server}/hello")
        assert res.from_cache == from_cache



@pytest.mark.skip('Flask 2 no longer lets us send a response without a reason')
def test_cache_can_handle_empty_http_reason(client, server) -> None:  # pragma: no cover
    for _from_cache_unused in (False, True):
        res = client.fetch(f"{server}/no-reason", raise_for_status=False)
        assert res.reason == ""
        assert res.text == "hello"
