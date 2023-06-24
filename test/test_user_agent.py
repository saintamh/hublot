#!/usr/bin/env python3

# standards
import re

# hublot
from hublot import HttpClient


def test_default_user_agent(server):
    client = HttpClient()
    user_agent = client.get(f'{server}/echo').json()['headers']['User-Agent']
    assert re.search(r'^hublot/[\d\.]+$', user_agent), user_agent


def test_user_agent_constructor_kwarg(server):
    client = HttpClient(user_agent='Nyanya/10.8')
    user_agent = client.get(f'{server}/echo').json()['headers']['User-Agent']
    assert user_agent == 'Nyanya/10.8'


def test_user_agent_method_kwarg(server):
    client = HttpClient(
        user_agent='this/gets/overriden',
    )
    user_agent = client.get(
        f'{server}/echo',
        user_agent='Prapra/12.12',
    ).json()['headers']['User-Agent']
    assert user_agent == 'Prapra/12.12'


def test_user_agent_in_headers(server):
    client = HttpClient()
    res = client.get(
        f'{server}/echo',
        headers={'User-Agent': 'Bwabwa/7.3'},
    )
    user_agent = res.json()['headers']['User-Agent']
    assert user_agent == 'Bwabwa/7.3'
