#!/usr/bin/env python3

# standards
from dataclasses import dataclass
from hashlib import md5
import re
from typing import Optional, Tuple, Union

# 3rd parties
from requests import PreparedRequest


UserSpecifiedCacheKey = Union['CacheKey', Tuple[str, ...], str]


@dataclass
class CacheKey:

    parts: Tuple[str, ...]

    @property
    def path_parts(self) -> Tuple[str, ...]:
        return tuple(
            re.sub(r'[^\w\-\.]', lambda m: f'%{ord(m.group()):02X}', part)
            for part in self.parts
        )

    @property
    def unique_str(self) -> str:
        # NB the string we return isn't for use in paths, so we can use '/' as the separator regardless of platform. Slashes have
        # been removed from the parts, so this is unambiguous.
        return '/'.join(self.path_parts)

    @classmethod
    def compute(cls, preq: PreparedRequest) -> 'CacheKey':
        # NB we don't normalise the order of the `params` dict or `data` dict. If running in Python 3.6+, where dicts preserve
        # their insertion order, multiple calls from the same code, where the params are defined in the same order, will hit the
        # same cache key. In previous versions, maybe not, so in 3.5 and before params and body should be serialised before being
        # sent to Forban.
        headers = sorted(
            (key.title(), value)
            for key, value in preq.headers.items()
        )
        key = (
            preq.method,
            preq.url,
            headers,
            preq.body,
        )
        # Shortening to 16 chars means it's easier to copy-paste, takes less space in the terminal, etc. Seems like a flimsy reason
        # for increasing the chances of a collision, but at 2^64 bits these chances are still comfortably negligible.
        hashed = md5(repr(key).encode('UTF-8')).hexdigest()[:16]
        return cls((hashed[:3], hashed[3:]))

    @classmethod
    def parse(cls, user_specified_key: Optional[UserSpecifiedCacheKey]):
        if isinstance(user_specified_key, CacheKey):
            return user_specified_key
        elif isinstance(user_specified_key, tuple):
            return cls(user_specified_key)
        elif isinstance(user_specified_key, str):
            return cls(tuple(user_specified_key.strip('/').split('/')))
        else:
            raise TypeError(repr(user_specified_key))
