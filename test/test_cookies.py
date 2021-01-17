#!/usr/bin/env python3

# 3rd parties
import pytest

# forban
from forban import Client


@pytest.mark.usefixtures('mocked_sleep')
def test_cookies_are_saved(client, server):
    assert client.get(f'{server}/cookies/get').json() == {}
    client.get(f'{server}/cookies/set?coo=kie')
    assert client.get(f'{server}/cookies/get').json() == {'coo': 'kie'}


@pytest.mark.usefixtures('mocked_sleep')
def test_cookies_are_set_when_running_from_cache(cache, server):
    for _ in (1, 2):
        client = Client(cache=cache)
        assert client.get(f'{server}/cookies/get').json() == {}
        client.get(f'{server}/cookies/set?coo=kie')
        assert client.get(f'{server}/cookies/get').json() == {'coo': 'kie'}


@pytest.mark.usefixtures('mocked_sleep')
def test_cached_redirects(cache, server):
    for _ in (1, 2):
        client = Client(cache=cache)
        client.get(f'{server}/redirect/chain/1')
        cookies = {c.name: c.value for c in client.session.cookies}
        assert cookies == {'redirect1': 'yes', 'redirect2': 'yes', 'redirect3': 'yes'}
