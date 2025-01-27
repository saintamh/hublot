#!/usr/bin/env python3

# standards
from datetime import timedelta
from itertools import combinations

# 3rd parties
import pytest

# hublot
from hublot import HttpClient

from .utils import dummy_compiled_request, dummy_response


@pytest.mark.parametrize(
    "courtesy_sleep",
    [None, timedelta(seconds=0), timedelta(seconds=5), timedelta(seconds=37)],
)
def test_courtesy_sleep(mocked_courtesy_sleep, server, courtesy_sleep):
    kwargs = {} if courtesy_sleep is None else {"courtesy_sleep": courtesy_sleep}
    client = HttpClient(**kwargs)
    client.fetch(f"{server}/hello")
    mocked_courtesy_sleep.assert_not_called()  # 1st request, no sleep
    client.fetch(f"{server}/hello")
    expected_sleep = 5 if courtesy_sleep is None else courtesy_sleep.total_seconds()
    if expected_sleep == 0:
        mocked_courtesy_sleep.assert_not_called()
    else:
        mocked_courtesy_sleep.assert_called_once()
        (delay,) = mocked_courtesy_sleep.call_args[0]
        assert delay == pytest.approx(expected_sleep, 0.1)


def test_method_kwarg_overrides_default(mocked_courtesy_sleep, server):
    client = HttpClient()
    client.fetch(f"{server}/hello")
    mocked_courtesy_sleep.assert_not_called()  # 1st request, no sleep
    client.fetch(f"{server}/hello", courtesy_sleep=timedelta(minutes=1))
    mocked_courtesy_sleep.assert_called_once()
    assert mocked_courtesy_sleep.call_args[0][0] == pytest.approx(60, 0.1)


def test_method_kwarg_zero_disables_courtesy_sleep(mocked_courtesy_sleep, server):
    client = HttpClient()
    client.fetch(f"{server}/hello")
    mocked_courtesy_sleep.assert_not_called()  # 1st request, no sleep
    client.fetch(f"{server}/hello", courtesy_sleep=timedelta(0))
    mocked_courtesy_sleep.assert_not_called()


def test_nonequal_hostnames(mocker, mocked_courtesy_sleep):
    client = HttpClient()
    mocker.patch.object(client.engine, "request", return_value=dummy_response(dummy_compiled_request(client)))
    client.fetch("http://one/")
    mocked_courtesy_sleep.assert_not_called()
    client.fetch("http://two/")
    mocked_courtesy_sleep.assert_not_called()


@pytest.mark.parametrize(
    "url_1, url_2",
    combinations(
        [
            # All of these are the same host, and so we should sleep between fetches of any pair of URLs in here
            "http://test/",
            "http://TEST/",
            "https://test/",
            "https://TEST/",
            "http://test:8080",
        ],
        2,
    ),
)
def test_equal_hostnames(mocker, mocked_courtesy_sleep, url_1, url_2):
    client = HttpClient()
    mocker.patch.object(client.engine, "request", return_value=dummy_response(dummy_compiled_request(client)))
    client.fetch(url_1)
    mocked_courtesy_sleep.assert_not_called()  # 1st request, no sleep
    client.fetch(url_2)
    mocked_courtesy_sleep.assert_called_once()
