#!/usr/bin/env python3

# standards
import re

# forban
from forban import scraper


def test_basic_logging(client, server, captured_logs):
    client.get(f'{server}/hello')
    assert re.search(fr'^\[\w\w\w/\w{{13}}\]          {server}/hello\n$', captured_logs())
    client.get(f'{server}/hello')
    assert re.search(fr'^\[\w\w\w/\w{{13}}\] \[cached\] {server}/hello\n$', captured_logs())


def test_logging_courtesy_sleep(client, server, captured_logs):
    client.get(f'{server}/echo?x=1')
    assert re.search(fr'^\[\w\w\w/\w{{13}}\]          {server}/echo\?x=1\n$', captured_logs())
    client.get(f'{server}/echo?x=2')
    assert re.search(fr'^\[\w\w\w/\w{{13}}\] \[  5s  \] {server}/echo\?x=2\n$', captured_logs())


def test_logging_redirects(client, server, captured_logs):
    client.get(f'{server}/redirect/chain/1')
    assert re.search(
        r'^'
        fr'\[\w\w\w/\w{{13}}\]          {server}/redirect/chain/1\n'
        fr'\[\w\w\w/\w{{13}}\]          -> {server}/redirect/chain/2\n'
        fr'\[\w\w\w/\w{{13}}\]          -> {server}/redirect/chain/3\n'
        r'$',
        captured_logs(),
    )


def test_logging_on_retry(client, server, captured_logs):
    @scraper
    def scrape():
        client.get(f'{server}/fail-twice-then-succeed/test_logging_on_retry')
        return 'ok'

    scrape()
    assert re.search(
        r'^'
        fr'\[\w\w\w/\w{{13}}\]          {server}/fail-twice-then-succeed/test_logging_on_retry\n'
        'HTTPError: 500 .+ sleeping 1s\n'
        fr'\[\w\w\w/\w{{13}}\]          {server}/fail-twice-then-succeed/test_logging_on_retry\n'
        'HTTPError: 500 .+ sleeping 5s\n'
        fr'\[\w\w\w/\w{{13}}\]          {server}/fail-twice-then-succeed/test_logging_on_retry\n'
        r'$',
        captured_logs(),
    )
