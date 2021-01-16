#!/usr/bin/env python3

# standards
from contextlib import contextmanager
import logging
from time import sleep, time
from typing import Any, Callable, Dict, Optional, Union
from urllib.parse import urlparse

# 3rd parties
from requests import Request, RequestException, Response, Session

# forban
from .cache import Cache
from .logs import LogEntry


class CourtesySleep:

    def __init__(self, courtesy_seconds: int):
        self.courtesy_seconds = courtesy_seconds
        self.last_request_per_host: Dict[str, float] = {}

    @contextmanager
    def __call__(self, req: Request, log: LogEntry, courtesy_seconds: Optional[int] = None):
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
        cache: Cache = None,
        session: Session = None,
        courtesy_sleep: Union[CourtesySleep, int] = 5,
        propagate_logs: bool = False,
    ):
        self.logger = self._init_logger(propagate_logs)
        self.cache = cache
        self.session = session or Session()
        if not isinstance(courtesy_sleep, CourtesySleep):
            courtesy_sleep = CourtesySleep(courtesy_sleep)  # malkovitch malkovitch
        self.courtesy_sleep = courtesy_sleep

    def fetch_and_parse(
        self,
        url: str,
        parse: Callable[[Response], Any],
        num_attempts: int=5,
        **kwargs,
    ) -> Any:
        for attempt in range(num_attempts):
            try:
                if attempt > 0:
                    kwargs['force_cache_stale'] = True
                return parse(self.fetch(url, **kwargs))
            except (ValueError, RequestException) as error:
                if attempt < num_attempts - 1:
                    delay = 5 ** attempt
                    self.logger.error('%s: %s - sleeping %ds', type(error).__name__, error, delay)
                    sleep(delay)
                else:
                    raise

    def fetch(
        self,
        url: str,
        force_cache_stale: bool = False,
        courtesy_seconds: Optional[int] = None,
        **kwargs,
    ) -> Response:
        method = kwargs.pop('method', 'GET').upper()
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

    def options(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='OPTIONS', **kwargs)

    def head(self, url: str, **kwargs) -> Response:
        kwargs.setdefault('allow_redirects', False)
        return self.fetch(url, method='HEAD', **kwargs)

    def post(self, url: str, data=None, json=None, **kwargs) -> Response:
        return self.fetch(url, method='POST', data=data, json=json, **kwargs)

    def put(self, url: str, data=None, **kwargs) -> Response:
        return self.fetch(url, method='PUT', data=data, **kwargs)

    def patch(self, url: str, data=None, **kwargs) -> Response:
        return self.fetch(url, method='PATCH', data=data, **kwargs)

    def delete(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='DELETE', **kwargs)

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
