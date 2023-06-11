#!/usr/bin/env python3

# 3rd parties
import pytest

# hublot
from hublot import HttpClient, HttpError


def test_http_error_is_raised(server):
    client = HttpClient()
    with pytest.raises(HttpError):
        client.get(f'{server}/fail-with-random-value')
