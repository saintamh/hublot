#!/usr/bin/env python3

# standards
from tempfile import TemporaryDirectory

# 3rd parties
import pytest

# melba
from melba import Storage


@pytest.fixture
def storage():
    with TemporaryDirectory() as temp_root:
        yield Storage(temp_root)
