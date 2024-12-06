#!/usr/bin/env python3

# standards
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

# 3rd parties
import pytest
import requests

# hublot
from hublot import Cache, HttpClient, HttpError, Request, TooManyRedirects
from hublot.cache.storage import DiskStorage


@pytest.mark.parametrize(
    "kwargs, expected_method",
    [
        ({}, "GET"),
        ({"data": None}, "GET"),
        ({"data": b""}, "POST"),
        ({"data": b"a=b"}, "POST"),
        ({"data": {"a": "b"}}, "POST"),
        ({"json": None}, "GET"),
        ({"json": ""}, "POST"),
        ({"json": {"a": "b"}}, "POST"),
    ],
)
def test_default_method(client, server, kwargs, expected_method) -> None:
    assert client.fetch(f"{server}/method-test", **kwargs).text == expected_method


def test_no_cache_by_default(server) -> None:
    client = HttpClient()
    one = client.get(f"{server}/unique-number").text
    two = client.get(f"{server}/unique-number").text
    assert one != two  # not cached


def test_null_cache(server) -> None:
    client = HttpClient(cache=None)
    one = client.get(f"{server}/unique-number").text
    two = client.get(f"{server}/unique-number").text
    assert one != two  # not cached


def test_cache_as_path(server) -> None:
    with TemporaryDirectory() as tmp:
        client = HttpClient(cache=Path(tmp))
        one = client.get(f"{server}/unique-number").text
        two = client.get(f"{server}/unique-number").text
    assert one == two  # cached


def test_cache_as_cache_object(server) -> None:
    with TemporaryDirectory() as tmp:
        client = HttpClient(cache=Cache(DiskStorage(Path(tmp))))
        one = client.get(f"{server}/unique-number").text
        two = client.get(f"{server}/unique-number").text
    assert one == two  # cached


def test_force_cache_stale(client, server) -> None:
    one = client.get(f"{server}/unique-number").text
    two = client.get(f"{server}/unique-number", force_cache_stale=True).text
    three = client.get(f"{server}/unique-number").text
    assert one != two  # cache not read on 2nd call
    assert two == three  # but cache was written on 2nd call


def test_courtesy_sleep_by_default(mocked_courtesy_sleep, server) -> None:
    client = HttpClient()
    client.get(f"{server}/unique-number")
    client.get(f"{server}/unique-number")
    mocked_courtesy_sleep.assert_called_once()
    (delay,) = mocked_courtesy_sleep.call_args[0]
    assert delay > 1


def test_null_courtesy_sleep(mocked_courtesy_sleep, server) -> None:
    client = HttpClient(courtesy_sleep=None)
    client.get(f"{server}/unique-number")
    client.get(f"{server}/unique-number")
    mocked_courtesy_sleep.assert_not_called()


def test_custom_courtesy_sleep(mocked_courtesy_sleep, server) -> None:
    client = HttpClient(courtesy_sleep=timedelta(minutes=2))
    client.get(f"{server}/unique-number")
    client.get(f"{server}/unique-number")
    mocked_courtesy_sleep.assert_called_once()
    (delay,) = mocked_courtesy_sleep.call_args[0]
    assert delay == pytest.approx(120, 0.1)


def test_http_errors_are_raised(client, server) -> None:
    with pytest.raises(HttpError):
        client.get(f"{server}/fail-with-random-value")


def test_auto_raise_can_be_disabled(client, server) -> None:
    res = client.get(f"{server}/fail-with-random-value", raise_for_status=False)
    assert res.status_code == 500
    assert not res.ok


def test_redirect(client, server) -> None:
    res = client.get(f"{server}/redirect/chain/1")
    assert res.status_code == 200
    assert res.ok
    assert res.text == "Landed"


def test_no_redirect(client, server) -> None:
    res = client.get(f"{server}/redirect/chain/1", allow_redirects=False)
    assert res.status_code == 302
    assert res.text == "Bounce 1"


def test_redirect_response_bodies(cache, server) -> None:
    for _ in (1, 2):
        client = HttpClient(cache=cache)
        res = client.get(f"{server}/redirect/chain/1")
        assert res.status_code == 200
        assert res.text == "Landed"


def test_redirects_set_response_history(cache, server) -> None:
    for _ in (1, 2):
        client = HttpClient(cache=cache)
        res = client.get(f"{server}/redirect/chain/1")
        assert [r.text for r in res.history] == ["Bounce 1", "Bounce 2"]


def test_redirect_loop(client, server) -> None:
    # Make sure that the caching doesn't interfere with Requests' ability to detect redirect loops
    with pytest.raises(TooManyRedirects):
        client.fetch(f"{server}/redirect/loop")


@pytest.mark.parametrize(
    "request_method, body_kwarg",
    [
        ("GET", None),
        ("POST", "data"),
        ("POST", "json"),
        ("SLURP", "data"),
    ],
)
@pytest.mark.parametrize(
    "redirect_code",
    [301, 302, 303, 307, 308],
)
@pytest.mark.parametrize(
    "params_as_dict",
    [True, False],
)
def test_redirect_method(client, server, request_method, body_kwarg, redirect_code, params_as_dict) -> None:
    expected_method_for_redirected_request = request_method if redirect_code in (307, 308) else "GET"
    params = {"code": redirect_code, "something": "else"}
    res = client.request(
        method=request_method,
        url=f"{server}/redirect" + ("" if params_as_dict else f"?{urlencode(params)}"),
        params=params if params_as_dict else None,
        data="blabla" if request_method != "GET" and body_kwarg == "data" else None,
        json={"bla": "bla"} if request_method != "GET" and body_kwarg == "json" else None,
        headers={"Magic": "Mushroom"},
    )
    payload = res.json()
    assert payload["headers"]["Magic"] == "Mushroom"
    assert payload["method"] == expected_method_for_redirected_request
    assert payload["args"] == {"something": "else"}
    assert payload["data"] == (
        "" if expected_method_for_redirected_request == "GET" else "blabla" if body_kwarg == "data" else '{"bla":"bla"}'
    )


def test_client_preserves_casing_of_percent_escapes_in_path(client, server) -> None:
    ref_upper = client.get(f"{server}/bicam%C3%A9ral").text
    assert ref_upper.startswith("upper")
    ref_lower = client.get(f"{server}/bicam%c3%a9ral").text
    assert ref_lower.startswith("lower")
    assert client.get(f"{server}/bicam%C3%A9ral").text == ref_upper
    assert client.get(f"{server}/bicam%c3%a9ral").text == ref_lower


def test_client_preserves_casing_of_percent_escapes_in_query(client, server) -> None:
    ref_upper = client.get(f"{server}/bicam%C3%A9ral?name=Zo%C3%A9").text
    assert ref_upper.startswith("upper")
    ref_lower = client.get(f"{server}/bicam%C3%A9ral?name=Zo%c3%a9").text
    assert ref_lower.startswith("lower")
    assert client.get(f"{server}/bicam%C3%A9ral?name=Zo%C3%A9").text == ref_upper
    assert client.get(f"{server}/bicam%C3%A9ral?name=Zo%c3%a9").text == ref_lower


def test_client_can_fetch_from_server_that_redirects_based_on_escape_code_case(client, server) -> None:
    url = f"{server}/redirig%C3%A9"
    with pytest.raises(requests.TooManyRedirects):
        requests.get(url, timeout=60)  # doesn't work with `requests`, boo
    assert client.get(url).text == "lower"  # Hublot can get around it though, hurray


def test_get_method(client, server) -> None:
    assert client.get(url=f"{server}/method-test").text == "GET"


def test_post_method(client, server) -> None:
    assert client.post(url=f"{server}/method-test").text == "POST"


def test_request_method(client, server) -> None:
    assert client.request(url=f"{server}/method-test", method="PUT").text == "PUT"


def test_setting_both_data_and_json(client) -> None:
    # `Request` objects are mutable, so we can conceivably allow having both fields set, as long as it's fixed before the request
    # is sent. So this raises no exception.
    req = Request(
        url="http://hublot.test/",
        data={"x": "1"},
        json={"x": "1"},
    )
    # This, however, raises an exception
    with pytest.raises(TypeError):
        client.fetch(req)


def test_client_level_headers_are_overriden_by_request_level(server) -> None:
    client = HttpClient(
        headers={
            "X-Test-1": "One",
            "X-Test-2": "Two",
        },
    )
    res = client.get(
        f"{server}/echo",
        headers={
            "X-Test-2": "Dva",
            "X-Test-3": "Tri",
        },
    )
    result = res.json()["headers"]
    print(result)
    assert result["X-Test-1"] == "One"
    assert result["X-Test-2"] == "Dva"
    assert result["X-Test-3"] == "Tri"
