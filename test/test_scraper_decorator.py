#!/usr/bin/env python3

# standards
from itertools import count

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
def test_scraper_decorator_on_http_error(client, server, unique_key):
    @scraper
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    assert fetch() == 'success after 2 failures'


@pytest.mark.usefixtures('mocked_sleep')
def test_scraper_decorator_on_value_error():
    counter = count()
    @scraper
    def fetch():
        i = next(counter)
        if i < 3:
            raise ValueError('x')
        return f'Success after {i} attempts'
    assert fetch() == 'Success after 3 attempts'


@pytest.mark.usefixtures('mocked_sleep')
def test_scraper_decorator_num_attempts(client, server, unique_key):
    @scraper(num_attempts=2)
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    with pytest.raises(ScraperError):
        fetch()


@pytest.mark.usefixtures('mocked_sleep')
def test_scraper_decorator_doesnt_catch_other_exceptions():
    @scraper
    def fetch():
        raise KeyError('x')
    with pytest.raises(KeyError):
        fetch()


@pytest.mark.usefixtures('mocked_sleep')
def test_scraper_decorator_retry_on():
    counter = count()
    @scraper(retry_on=[KeyError])
    def fetch():
        i = next(counter)
        if i < 3:
            raise KeyError('x')
        return f'Success after {i} attempts'
    assert fetch() == 'Success after 3 attempts'
