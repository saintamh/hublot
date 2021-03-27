#!/usr/bin/env python3

# 3rd parties
from requests import Request

# forban
from forban import RequestableABC


def test_requestable_is_runtime_type():
    """ `forban.RequestableABC` is not a type annotation, it's an ABC class that can be used with `isinstance` """
    assert isinstance('http://blah/', RequestableABC)
    assert isinstance(Request('GET', 'http://blah/'), RequestableABC)
