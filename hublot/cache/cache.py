#!/usr/bin/env python3

# standards
from datetime import timedelta
from pathlib import Path
from typing import Optional, Union

# hublot
from ..datastructures import CompiledRequest, Response
from ..logs import LogEntry
from .key import CacheKey, UserSpecifiedCacheKey
from .storage import DiskStorage, Storage


class Cache:

    def __init__(
        self,
        storage: Storage,
        max_age_overall: Optional[timedelta] = None,
    ) -> None:
        self.storage = storage
        self.max_age_overall = max_age_overall
        self.has_been_pruned = False

    def get(
        self,
        creq: CompiledRequest,
        log: LogEntry,
        max_age: Optional[timedelta] = None,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> Optional[Response]:
        """
        Looks up the given `CompiledRequest`, and returns the corresponding `Response` if it was in cache, or `None` otherwise.
        """
        key = CacheKey.parse(key) if key else CacheKey.compute(creq)
        if self.max_age_overall is not None and not self.has_been_pruned:
            self.storage.prune(self.max_age_overall)
            self.has_been_pruned = True
        if max_age is None or (self.max_age_overall is not None and max_age > self.max_age_overall):
            # The `max_age` passed to the method can't be greater than that given to the constructor, that would be inconsistent
            # with the cache pruning that happens and which is always based on the constructor-given `self.max_age_overall`
            max_age = self.max_age_overall
        res = self.storage.read(key, max_age)
        log.cached = res is not None
        log.cache_key_str = key.unique_str
        return res

    def put(
        self,
        creq: CompiledRequest,
        log: LogEntry,
        res: Response,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> None:
        key = CacheKey.parse(key) if key else CacheKey.compute(creq)
        log.cache_key_str = key.unique_str
        self.storage.write(key, res)


CacheSpec = Union[Cache, Path, str, None]


def load_cache(
    cache: CacheSpec = None,
    max_age_overall: Optional[timedelta] = None,
) -> Optional['Cache']:
    """
    Takes the `cache` param given to the `HttpClient` constructor, and returns a `Cache` instance, or `None`
    """
    if cache is None or isinstance(cache, Cache):
        if max_age_overall is not None:
            raise TypeError("You can't specify a max_age if passing in an already instantiated `Cache`")
        return cache
    elif isinstance(cache, Path):
        return Cache(
            storage=DiskStorage(root_path=cache),
            max_age_overall=max_age_overall,
        )
    elif isinstance(cache, str) and cache.startswith('redis://'):  # pragma: no cover
        raise NotImplementedError  # some day
    else:
        raise TypeError(repr(cache))
