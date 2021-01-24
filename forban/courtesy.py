#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from datetime import timedelta
from time import sleep, time
from typing import Dict, Optional, Union
from urllib.parse import urlparse

# 3rd parties
from requests import PreparedRequest

# forban
from .logs import LogEntry


class CourtesySleep:

    def __init__(self, courtesy_seconds: Optional[Union[float, timedelta]]):
        if courtesy_seconds is None:
            courtesy_seconds = 0
        elif isinstance(courtesy_seconds, timedelta):
            courtesy_seconds = courtesy_seconds.total_seconds()
        self.courtesy_seconds = courtesy_seconds
        self.last_request_per_host: Dict[str, float] = {}

    @contextmanager
    def __call__(self, preq: PreparedRequest, log: LogEntry, courtesy_seconds: Optional[float] = None):
        if courtesy_seconds is None:
            courtesy_seconds = self.courtesy_seconds
        host = str(urlparse(preq.url).hostname)
        last_request = self.last_request_per_host.get(host, 0)
        delay = (last_request + courtesy_seconds) - time()
        if delay > 0:
            log.courtesy_seconds = delay
            sleep(delay)
        try:
            yield
        finally:
            # NB we store the time after the request is complete
            self.last_request_per_host[host] = time()
