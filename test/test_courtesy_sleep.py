#!/usr/bin/env python3

# You're confused because we're patching the `sleep` function and it's not what you expect, pylint: disable=no-member

# standards
from itertools import combinations

# 3rd parties
import pytest

# forban
import forban
from .utils import dummy_response


@pytest.mark.parametrize(
    'courtesy_seconds',
    [None, 0, 5, 37],
)
def test_courtesy_sleep(mocker, server, courtesy_seconds):
    kwargs = {} if courtesy_seconds is None else {'courtesy_sleep': courtesy_seconds}
    client = forban.Client(**kwargs)
    mocker.patch('forban.forban.sleep')
    client.fetch(f'{server}/hello')
    forban.forban.sleep.assert_not_called()  # 1st request, no sleep
    client.fetch(f'{server}/hello')
    if courtesy_seconds == 0:
        forban.forban.sleep.assert_not_called()
    else:
        forban.forban.sleep.assert_called_once()
        delay, = forban.forban.sleep.call_args[0]
        assert delay == pytest.approx(courtesy_seconds or 5, 0.1)


def test_nonequal_hostnames(mocker):
    client = forban.Client()
    mocker.patch('forban.forban.sleep')
    mocker.patch.object(client.session, 'request', return_value=dummy_response())
    client.fetch('http://one/')
    forban.forban.sleep.assert_not_called()
    client.fetch('http://two/')
    forban.forban.sleep.assert_not_called()


@pytest.mark.parametrize(
    'url_1, url_2',
    combinations(
        [
            # All of these are the same host, and so we should sleep between fetches of any pair of URLs in here
            'http://test/',
            'http://TEST/',
            'https://test/',
            'https://TEST/',
            'http://test:8080',
        ],
        2,
    )
)
def test_equal_hostnames(mocker, url_1, url_2):
    client = forban.Client()
    mocker.patch('forban.forban.sleep')
    mocker.patch.object(client.session, 'request', return_value=dummy_response())
    client.fetch(url_1)
    forban.forban.sleep.assert_not_called()  # 1st request, no sleep
    client.fetch(url_2)
    forban.forban.sleep.assert_called_once()
