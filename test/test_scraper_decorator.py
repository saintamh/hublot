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


def test_scraper_decorator_on_http_error(client, server, unique_key):
    @scraper
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    assert fetch() == 'success after 2 failures'


def test_scraper_decorator_on_value_error():
    counter = count()
    @scraper
    def fetch():
        i = next(counter)
        if i < 3:
            raise ValueError('x')
        return f'Success after {i} attempts'
    assert fetch() == 'Success after 3 attempts'


def test_scraper_decorator_num_attempts(client, server, unique_key):
    @scraper(num_attempts=2)
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    with pytest.raises(ScraperError):
        fetch()


def test_scraper_decorator_doesnt_catch_other_exceptions():
    @scraper
    def fetch():
        raise KeyError('x')
    with pytest.raises(KeyError):
        fetch()


def test_scraper_decorator_retry_on():
    counter = count()
    @scraper(retry_on=[KeyError])
    def fetch():
        i = next(counter)
        if i < 3:
            raise KeyError('x')
        return f'Success after {i} attempts'
    assert fetch() == 'Success after 3 attempts'


def test_if_scraper_returns_generator_it_gets_consumed():
    @scraper
    def fetch():
        yield 1
        yield 2
        yield 3
    assert fetch() == [1, 2, 3]


def test_if_scraper_returns_iterator_it_gets_consumed():
    @scraper
    def fetch():
        return (i for i in range(1, 4))
    assert fetch() == [1, 2, 3]
