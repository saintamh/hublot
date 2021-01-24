#!/usr/bin/env python3

# standards
from pathlib import Path
from typing import Optional, Union

# 3rd parties
from requests import PreparedRequest, Response

# forban
from ..logs import LogEntry
from .key import CacheKey, UserSpecifiedCacheKey
from .storage import DiskStorage, Storage


class Cache:

    def __init__(self, storage: Storage):
        self.storage = storage

    def get(
        self,
        preq: PreparedRequest,
        log: LogEntry,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> Optional[Response]:
        """
        Looks up the given `PreparedRequest`, and returns the corresponding `Response` if it was in cache, or `None` otherwise.
        """
        key = CacheKey.parse(key) if key else CacheKey.compute(preq)
        res = self.storage.read(key)
        if res is not None:
            res.request = preq  # the storage doesn't need to store and recreate the request
            log.cached = True
        else:
            res = None
            log.cached = False
        log.cache_key_str = key.unique_str
        return res

    def put(
        self,
        preq: PreparedRequest,
        res: Response,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> None:
        key = CacheKey.parse(key) if key else CacheKey.compute(preq)
        self.storage.write(key, res)

    @classmethod
    def load(cls, cache: Optional[Union['Cache', Path, str]] = None) -> Optional['Cache']:
        """
        Takes the `cache` param given to the `Client` constructor, and returns a `Cache` instance, or `None`
        """
        if cache is None or isinstance(cache, Cache):
            return cache
        elif isinstance(cache, Path):
            return cls(storage=DiskStorage(root_path=cache))
        elif isinstance(cache, str) and cache.startswith('s3://'):
            raise NotImplementedError  # some day
        else:
            raise ValueError(repr(cache))
