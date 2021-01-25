#!/usr/bin/env python3

# standards
from datetime import datetime, timedelta


def _fetch_unique_number_then_move_clock_to_next_day(mocker, reinstantiable_client, server):
    now = datetime.now()
    client = reinstantiable_client()
    unique = client.get(f'{server}/unique-number').text
    mocker.patch('forban.cache.storage.current_datetime', return_value=now + timedelta(days=1))
    return unique


def test_cache_max_age_defaults(mocker, reinstantiable_client, server):
    # no max_age specified, cache is still valid a day later
    unique = _fetch_unique_number_then_move_clock_to_next_day(mocker, reinstantiable_client, server)
    client = reinstantiable_client()
    assert unique == client.get(f'{server}/unique-number').text


def test_cache_long_max_age(mocker, reinstantiable_client, server):
    # max_age is 2 days, cache is still valid a day later
    unique = _fetch_unique_number_then_move_clock_to_next_day(mocker, reinstantiable_client, server)
    client = reinstantiable_client()
    assert unique == client.get(f'{server}/unique-number', max_cache_age=timedelta(days=2)).text


def test_cache_short_max_age(mocker, reinstantiable_client, server):
    # max_age is 12 hours, cache is no longer valid a day later, we get a new `unique` number
    unique = _fetch_unique_number_then_move_clock_to_next_day(mocker, reinstantiable_client, server)
    client = reinstantiable_client()
    assert unique != client.get(f'{server}/unique-number', max_cache_age=timedelta(hours=12)).text


def test_cache_pruning(mocker, reinstantiable_client, server):
    # client is created with max_age of 12 hours, and a request (of any URL) is run. The cache gets pruned.
    unique = _fetch_unique_number_then_move_clock_to_next_day(mocker, reinstantiable_client, server)
    client = reinstantiable_client(max_age=timedelta(hours=12))
    client.get(f'{server}/hello')
    # now it's no longer cached, we fetch a new `unique` number
    client = reinstantiable_client()
    assert unique != client.get(f'{server}/unique-number').text


def test_override_with_method_kwarg(mocker, reinstantiable_client, server):
    # instantiate cache with a max_age that would accept the cached file, but then call the get() method with a shorter age -- the
    # method kwarg overrides the constructor kwarg, cache is invalidated, a new value is fetched
    unique = _fetch_unique_number_then_move_clock_to_next_day(mocker, reinstantiable_client, server)
    client = reinstantiable_client(max_age=timedelta(days=10))
    assert unique != client.get(f'{server}/unique-number', max_cache_age=timedelta(hours=12)).text


def test_cant_override_with_longer_age(mocker, reinstantiable_client, server):
    # instantiate cache with a max_age that doesn't accept the cached file. Try overriding it with a longer max_cache_age -- that
    # doesn't work. The constructor-given max_cache_age is an upper bound on what the method kwarg accepts (to stay consistent with
    # the fact that the constructor-given max_cache_age triggers full prunes)
    now = datetime.now()
    client = reinstantiable_client(max_age=timedelta(hours=12))
    unique = client.get(f'{server}/unique-number').text
    mocker.patch('forban.cache.storage.current_datetime', return_value=now + timedelta(days=1))
    # re-use the same client to ensure there's no pruning happening, that would render the test invalid
    assert unique != client.get(f'{server}/unique-number', max_cache_age=timedelta(days=2)).text


def test_cant_override_with_null_age(mocker, reinstantiable_client, server):
    # instantiate cache with a max_age that doesn't accept the cached file. Try overriding it with max_cache_age=None -- that also
    # doesn't work, we fall back to the constructor-given kwarg
    now = datetime.now()
    client = reinstantiable_client(max_age=timedelta(hours=12))
    unique = client.get(f'{server}/unique-number').text
    mocker.patch('forban.cache.storage.current_datetime', return_value=now + timedelta(days=1))
    # again, re-use the same client to ensure there's no pruning
    assert unique != client.get(f'{server}/unique-number', max_cache_age=None).text
