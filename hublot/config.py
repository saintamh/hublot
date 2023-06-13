#!/usr/bin/env python3

# standards
from collections.abc import Container
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Dict, Optional, Tuple, Union

# hublot
from .version import HUBLOT_VERSION


# Headers in this set will not be taken into account when computing cache keys, so two requests with different values for these
# headers will still get the same cache key.
#
DEFAULT_HEADERS_IGNORED_BY_CACHE = frozenset([
    # By excluding User-Agent from cache we can upgrade Hublot, or fake a more recent browser, without zapping the entire cache.
    'User-Agent',
])


@dataclass
class Config:
    allow_redirects: bool = True
    cookies_enabled: bool = True
    courtesy_sleep: Optional[timedelta] = timedelta(seconds=5)
    force_cache_stale: bool = False
    headers_ignored_by_cache: Container[str] = DEFAULT_HEADERS_IGNORED_BY_CACHE
    max_cache_age: Optional[timedelta] = None
    max_redirects: int = 10
    proxies: Optional[Dict[str, str]] = None
    raise_for_status: bool = True
    timeout: Optional[int] = 60
    user_agent: Optional[str] = f'hublot/{HUBLOT_VERSION}'
    verify: Optional[bool] = True

    def derive_using_kwargs(self, **kwargs: object) -> Tuple['Config', Dict[str, object]]:
        # NB this must always return a new instance, so that the caller can modify it without affecting the original
        config = Config(**{  # type: ignore
            key: kwargs.pop(key, default)
            for key, default in asdict(self).items()
        })
        return config, kwargs
