#!/usr/bin/env python3

# standards
from itertools import count

# 3rd parties
import pytest

# forban
from forban import ScraperError, retry_on_scraper_error


def test_retry_decorator_no_exception(client, server):
    @retry_on_scraper_error
    def fetch():
        return client.get(f'{server}/hello').text
    assert fetch() == 'hello'


def test_retry_decorator_on_http_error(client, server, unique_key):
    @retry_on_scraper_error
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    assert fetch() == 'success after 2 failures'


def test_retry_decorator_on_value_error():
    counter = count()
    @retry_on_scraper_error
    def fetch():
        i = next(counter)
        if i < 3:
            raise ValueError('x')
        return f'Success on attempt {i}'
    assert fetch() == 'Success on attempt 3'


def test_retry_decorator_num_attempts_just_enough(client, server, unique_key):
    @retry_on_scraper_error(num_attempts=3)
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    assert fetch() == 'success after 2 failures'


def test_retry_decorator_num_attempts_just_not_enough(client, server, unique_key):
    @retry_on_scraper_error(num_attempts=2)
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    with pytest.raises(ScraperError):
        fetch()


def test_retry_decorator_doesnt_catch_other_exceptions():
    @retry_on_scraper_error
    def fetch():
        raise KeyError('x')
    with pytest.raises(KeyError):
        fetch()


def test_retry_decorator_error_types():
    counter = count()
    @retry_on_scraper_error(error_types=[KeyError])
    def fetch():
        i = next(counter)
        if i < 3:
            raise KeyError('x')
        return f'Success on attempt {i}'
    assert fetch() == 'Success on attempt 3'


def test_if_scraper_returns_generator_it_gets_consumed():
    @retry_on_scraper_error
    def fetch():
        yield 1
        yield 2
        yield 3
    assert fetch() == [1, 2, 3]


def test_if_scraper_returns_iterator_it_gets_consumed():
    @retry_on_scraper_error
    def fetch():
        return (i for i in range(1, 4))
    assert fetch() == [1, 2, 3]


def test_scraper_sleeps_increasingly_long_delays(mocked_sleep_on_retry):
    """
    The first sleep must be >= 0 seconds, and then they must all be > than the previous
    """
    counter = count()
    @retry_on_scraper_error
    def fetch():
        i = next(counter)
        if i < 4:
            raise ValueError('x')
        return f'Success on attempt {i}'
    assert fetch() == 'Success on attempt 4'
    assert mocked_sleep_on_retry.call_count == 4
    previous_sleep = -1
    for attempt in range(4):
        called_args = mocked_sleep_on_retry.call_args_list[attempt][0]
        assert len(called_args) == 1, called_args
        sleep, = called_args
        assert sleep > previous_sleep
        previous_sleep = sleep


def test_no_courtesy_sleep_on_retries(mocked_courtesy_sleep, client, server, unique_key):
    client.get(f'{server}/hello')
    @retry_on_scraper_error
    def fetch():
        return client.get(f'{server}/fail-twice-then-succeed/{unique_key}').text
    fetch()
    sleeps = [call[0][0] for call in mocked_courtesy_sleep.call_args_list]
    # we should've slept on the 1st call b/c we'd just called the server, then no sleep on subsequent calls
    assert sleeps == [pytest.approx(5, 0.1)]
