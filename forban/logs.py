#!/usr/bin/env python3

# standards
from dataclasses import dataclass
from typing import Optional

# 3rd parties
from requests import PreparedRequest


@dataclass(frozen=False)
class LogEntry:
    prepared_req: PreparedRequest
    cache_key: Optional[str] = None
    cached: Optional[bool] = None
    courtesy_seconds: Optional[float] = None

    def _compose_line(self):
        if self.cache_key:
            yield f'[{self.cache_key}] '
        if self.cached:
            yield '[cached] '
        elif (self.courtesy_seconds or 0) > 0.5:
            seconds = f'{round(self.courtesy_seconds)}s'
            yield f'[{seconds:^6s}] '
        else:
            yield '         '
        pr = self.prepared_req
        yield pr.url
        if pr.method != 'GET':
            yield f'[{pr.method}'
            try:
                length = int(pr.headers.get('Content-Length', 0))
            except ValueError:
                length = 0
            if length > 0:
                yield f' {length} bytes'
            yield ']'

    def __str__(self):
        return ''.join(self._compose_line())
