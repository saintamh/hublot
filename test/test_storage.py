#!/usr/bin/env python3

# standards
import gzip

# 3rd parties
import pytest

# forban
from forban.cache import CacheKey
from .utils import dummy_response


def test_header_storage(header_storage):
    key = CacheKey.parse('somestring')
    assert header_storage.select(key) is None
    res = dummy_response()
    res.content  # it's to to consume the data to memory, pylint: disable=pointless-statement
    res._content = None  # pylint: disable=protected-access
    header_storage.insert(key, res)
    retrieved = header_storage.select(key)
    assert retrieved.__getstate__() == res.__getstate__()


@pytest.mark.parametrize(
    'body',
    [
        b'',
        b'hello',
        b'hello' * 1000
    ],
)
def test_body_storage(body_storage, body):
    key = CacheKey.parse('somestring')
    body_storage.write(key, body)
    assert body_storage.read(key) == body


def test_body_storage_files_contain_gzipped_body(body_storage):
    """
    This is part of the contract for BodyStorage -- the files stored on disk are just the gzipped body
    """
    assert not list(body_storage.root_path.glob('**/*'))
    key = CacheKey.parse('somestring')
    body = b'This is my response body.'
    body_storage.write(key, body)
    body_file, = body_storage.root_path.glob('**/*')
    with gzip.open(body_file, 'rb') as file_in:
        assert file_in.read() == body


def test_body_storage_file_paths_follow_cache_key_parts(body_storage):
    assert not list(body_storage.root_path.glob('**/*'))
    key = CacheKey.parse(('one', 'two', 'tree'))
    body = b'This is my response body.'
    body_storage.write(key, body)
    body_file, = body_storage.root_path.glob('**/*.*')
    assert body_file == body_storage.root_path / 'one' / 'two' / 'tree.gz'
