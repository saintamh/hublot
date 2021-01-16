#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from datetime import timedelta
from functools import wraps
import logging
from pathlib import Path
from time import sleep, time
from typing import Callable, Dict, Optional, Union, Tuple
from urllib.parse import urlparse

# 3rd parties
from requests import Request, RequestException, Response, Session

# forban
from .cache import Cache
from .logs import LogEntry


DEFAULT_LOGGER = logging.getLogger('forban')


class CourtesySleep:

    def __init__(self, courtesy_seconds: Optional[Union[float, timedelta]]):
        if courtesy_seconds is None:
            courtesy_seconds = 0
        elif isinstance(courtesy_seconds, timedelta):
            courtesy_seconds = courtesy_seconds.total_seconds()
        self.courtesy_seconds = courtesy_seconds
        self.last_request_per_host: Dict[str, float] = {}

    @contextmanager
    def __call__(self, req: Request, log: LogEntry, courtesy_seconds: Optional[float] = None):
        if courtesy_seconds is None:
            courtesy_seconds = self.courtesy_seconds
        host = urlparse(req.url).hostname
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


class Client:

    def __init__(
        self,
        cache: Optional[Union[Path, Cache]] = None,
        courtesy_sleep: Optional[Union[CourtesySleep, float, timedelta]] = 5,
        session: Optional[Session] = None,
        propagate_logs: bool = False,
    ):
        self.logger = self._init_logger(propagate_logs)
        if isinstance(cache, Path):
            cache = Cache(cache)
        self.cache = cache
        if not isinstance(courtesy_sleep, CourtesySleep):
            courtesy_sleep = CourtesySleep(courtesy_sleep)  # malkovitch malkovitch
        self.courtesy_sleep = courtesy_sleep
        self.session = session or Session()

    def fetch(
        self,
        url: str,
        force_cache_stale: bool = False,
        courtesy_seconds: Optional[float] = None,
        **kwargs,
    ) -> Response:
        default_method = (
            'POST' if (kwargs.get('data') is not None or kwargs.get('files') is not None or kwargs.get('json') is not None)
            else 'GET'
        )
        method = kwargs.pop('method', default_method).upper()
        req = Request(
            url=url,
            method=method,
            headers=kwargs.get('headers'),
            files=kwargs.get('files'),
            data=kwargs.get('data') or {},
            json=kwargs.get('json'),
            params=kwargs.get('params') or {},
            auth=kwargs.get('auth'),
            cookies=kwargs.get('cookies'),
        )
        prepared_req = self.session.prepare_request(req)
        log = LogEntry(prepared_req)
        res = None
        if self.cache and not force_cache_stale:
            res = self.cache.get(prepared_req, log)
        if res is None:
            with self.courtesy_sleep(req, log, courtesy_seconds):
                res = self.session.request(method, url, **kwargs)
            if self.cache:
                self.cache.put(prepared_req, res)
        self.logger.info('%s', log)
        return res

    def get(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='GET', **kwargs)

    def post(self, url: str, data=None, json=None, **kwargs) -> Response:
        return self.fetch(url, method='POST', data=data, json=json, **kwargs)

    @staticmethod
    def _init_logger(propagate: bool):
        logger = logging.getLogger('forban')
        if not propagate:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s', None, '%')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False
        return logger


def scraper(
    no_parens_function: Optional[Callable] = None,
    *,
    retry_on: Tuple[type, ...] = (ValueError, RequestException),
    logger: logging.Logger = DEFAULT_LOGGER,
    num_attempts: int = 5,
):
    if no_parens_function:
        # decorator is without parentheses
        return scraper()(no_parens_function)

    def make_wrapper(function: Callable):

        @wraps(function)
        def wrapper(*args, **kwargs):
            for attempt in range(num_attempts):
                try:
                    # if attempt > 0:
                    #     kwargs['force_cache_stale'] = True
                    return function(*args, **kwargs)
                except Exception as error:  # pylint: disable=broad-except
                    if isinstance(error, retry_on) and attempt < num_attempts - 1:
                        delay = 5 ** attempt
                        logger.error('%s: %s - sleeping %ds', type(error).__name__, error, delay)
                        sleep(delay)
                    else:
                        raise

        return wrapper
    return make_wrapper
