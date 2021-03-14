#!/usr/bin/env python3

# 3rd parties
from requests import Request

# forban
from forban import Requestable


def test_requestable_is_runtime_type():
    """ `forban.Requestable` is not just a type annotation, it's a real class that can be used with `isinstance` """
    assert isinstance('http://blah/', Requestable)
    assert isinstance(Request('GET', 'http://blah/'), Requestable)
