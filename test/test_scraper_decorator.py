#!/usr/bin/env python3

# 3rd parties
import pytest

# forban
from forban import ScraperError, scraper


def test_scraper_decorator_no_exception(client, server):
    @scraper
    def fetch():
        return client.get(f'{server}/hello').text
    assert fetch() == 'hello'


@pytest.mark.usefixtures('mocked_sleep')
def test_scraper_decorator_on_failure(client, server, unique_key):
    @scraper
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    assert fetch() == 'success after 2 failures'


@pytest.mark.usefixtures('mocked_sleep')
def test_scraper_decorator_num_attempts(client, server, unique_key):
    @scraper(num_attempts=2)
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    with pytest.raises(ScraperError):
        fetch()
