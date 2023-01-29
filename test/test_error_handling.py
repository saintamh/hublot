#!/usr/bin/env python3

# 3rd parties
import pytest

# hublot
from hublot import SCRAPER_ERROR_TYPES, Client, ScraperError


def test_scraper_error_is_raised(server):
    client = Client()
    with pytest.raises(ScraperError):
        client.get(f'{server}/fail-with-random-value')


def test_scraper_error_can_be_caught_using_error_types_tuple(server):
    client = Client()
    caught = False
    try:
        client.get(f'{server}/fail-with-random-value')
    except ScraperError:
        pytest.fail('this is not expected to work')
    except SCRAPER_ERROR_TYPES:
        caught = True
    assert caught
