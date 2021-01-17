#!/usr/bin/env python3

# standards
import random
from string import ascii_letters

# 3rd parties
import pytest

# forban
from forban import scraper


def test_scraper_decorator_no_exception(client, server):

    @scraper
    def fetch():
        return client.get(f'{server}/hello').text

    assert fetch() == 'hello'


@pytest.mark.usefixtures('mocked_sleep')
def test_scraper_decorator_on_failure(client, server):
    key = ''.join(random.choices(ascii_letters, k=32))

    @scraper
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{key}').text

    assert fetch() == 'success after 2 failures'
