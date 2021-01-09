#!/usr/bin/env python3

# standards
from tempfile import TemporaryDirectory

# 3rd parties
import pytest

# melba
from melba import Cache, Storage


@pytest.fixture
def storage():
    with TemporaryDirectory() as temp_root:
        yield Storage(temp_root)


@pytest.fixture
def cache():
    with TemporaryDirectory() as temp_root:
        yield Cache(temp_root)
