#!/usr/bin/env python3

# standards
from pathlib import Path
from typing import Optional, Union

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, Response
from ..logs import LogEntry
from .key import CacheKey, UserSpecifiedCacheKey
from .storage import DiskStorage, Storage


class Cache:

    def __init__(
        self,
        storage: Storage,
        config: Config = Config(),
    ) -> None:
        self.storage = storage
        self.config = config
        self.max_age_overall = config.max_cache_age
        self.has_been_pruned = False

    def get(
        self,
        creq: CompiledRequest,
        log: LogEntry,
        config: Optional[Config] = None,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> Optional[Response]:
        """
        Looks up the given `CompiledRequest`, and returns the corresponding `Response` if it was in cache, or `None` otherwise.
        """
        if config is None:
            config = self.config
        key = CacheKey.parse(key) if key else CacheKey.compute(creq, config)
        if self.max_age_overall is not None and not self.has_been_pruned:
            self.storage.prune(self.max_age_overall)
            self.has_been_pruned = True
        max_age = config.max_cache_age
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
        config: Optional[Config] = None,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> None:
        if config is None:
            config = self.config
        key = CacheKey.parse(key) if key else CacheKey.compute(creq, config)
        log.cache_key_str = key.unique_str
        self.storage.write(key, res)


CacheSpec = Union[Cache, Path, str, None]


def load_cache(
    cache: CacheSpec = None,
    config: Config = Config(),
) -> Optional["Cache"]:
    """
    Takes the `cache` param given to the `HttpClient` constructor, and returns a `Cache` instance, or `None`
    """
    if cache is None or isinstance(cache, Cache):
        return cache
    elif isinstance(cache, Path):
        return Cache(
            storage=DiskStorage(root_path=cache),
            config=config,
        )
    elif isinstance(cache, str) and cache.startswith("redis://"):  # pragma: no cover
        raise NotImplementedError  # some day
    else:
        raise TypeError(repr(cache))
