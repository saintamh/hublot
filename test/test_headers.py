#!/usr/bin/env python3

# 3rd parties
import pytest

# hublot
from hublot import Headers


def test_empty_headers() -> None:
    headers = Headers()
    assert not headers
    assert headers.get("anything") is None
    with pytest.raises(KeyError):
        print(headers["anything"])
    assert list(headers.get_all("Anything")) == []
    assert list(headers) == []
    assert list(headers.keys()) == []
    assert list(headers.items()) == []
    assert headers == Headers()
    assert headers != Headers({"My-Key": "My-Value"})
    assert headers != {}  # never equal to sth that isn't a Headers object


def test_add_method() -> None:
    headers = Headers()
    headers.add("My-Key", "My-Value")
    assert headers
    assert "My-Key" in headers
    assert headers["My-Key"] == "My-Value"
    with pytest.raises(KeyError):
        print(headers["anything else"])
    assert list(headers.get_all("My-Key")) == ["My-Value"]
    assert list(headers) == ["My-Key"]
    assert list(headers.keys()) == ["My-Key"]
    assert list(headers.items()) == [("My-Key", "My-Value")]
    assert headers == Headers({"My-Key": "My-Value"})
    assert headers != {"My-Key": "My-Value"}


def test_constructor_arg() -> None:
    headers = Headers({})
    headers.add("My-Key", "My-Value")
    assert headers == Headers({"My-Key": "My-Value"})


def test_case_insensitivity() -> None:
    headers = Headers()
    headers.add("My-Key", "My-Value")
    assert headers["My-Key"] == "My-Value"
    assert headers["my-key"] == "My-Value"
    assert headers["mY-kEY"] == "My-Value"
    assert "My-Key" in headers
    assert "my-key" in headers
    assert "mY-kEY" in headers
    assert list(headers.get_all("my-key")) == ["My-Value"]


def test_key_case_is_preserved() -> None:
    headers = Headers()
    headers.add("my-key", "My-Value")
    assert list(headers) == ["my-key"]
    assert list(headers.keys()) == ["my-key"]
    assert list(headers.items()) == [("my-key", "My-Value")]
    assert list(headers.items(normalise_keys=True)) == [("My-Key", "My-Value")]


def test_eq() -> None:
    assert Headers({"My-Key": "My-Value"}) == Headers({"my-key": "My-Value"})
    assert Headers({"My-Key": "My-Value"}) != Headers({"My-Key": "vALUE"})


def test_multiple_values() -> None:
    headers = Headers()
    headers.add("My-Key", "My-Value-1")
    headers.add("My-Key", "My-Value-2")
    headers.add("My-Key", "My-Value-3")
    assert list(headers) == ["My-Key"]
    assert list(headers.items()) == [("My-Key", "My-Value-1"), ("My-Key", "My-Value-2"), ("My-Key", "My-Value-3")]
    assert headers.get("My-Key") == "My-Value-1; My-Value-2; My-Value-3"


def test_setdefault() -> None:
    headers = Headers()
    headers.setdefault("My-Key", "My-Value-1")
    headers.setdefault("My-Key", "My-Value-2")
    assert headers["My-Key"] == "My-Value-1"


def test_repr() -> None:
    # We don't check the specifics of the repr format, but we do check that the values are included
    headers = Headers()
    headers.add("My-Key", "My-Value-1")
    headers.add("My-Key", "My-Value-2")
    assert "My-Key" in repr(headers)
    assert "My-Value-1" in repr(headers)
    assert "My-Value-2" in repr(headers)
