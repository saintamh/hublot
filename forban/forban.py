#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from functools import wraps
import logging
from pathlib import Path
import threading
from time import sleep, time
from typing import Any, Callable, Dict, Optional, Union, Tuple
from urllib.parse import urlparse

# 3rd parties
from requests import PreparedRequest, Request, Response, Session
from requests.cookies import MockRequest

# forban
from .cache import Cache
from .exceptions import ScraperError
from .logs import LogEntry


DEFAULT_LOGGER = logging.getLogger('forban')


@dataclass
class ThreadLocalData:
    scraper_kwargs: Dict[str, Any] = field(default_factory=dict)
    logger: Optional[logging.Logger] = None


_SCRAPER_LOCAL = threading.local()
_SCRAPER_LOCAL.stack = [ThreadLocalData()]


class CourtesySleep:

    def __init__(self, courtesy_seconds: Optional[Union[float, timedelta]]):
        if courtesy_seconds is None:
            courtesy_seconds = 0
        elif isinstance(courtesy_seconds, timedelta):
            courtesy_seconds = courtesy_seconds.total_seconds()
        self.courtesy_seconds = courtesy_seconds
        self.last_request_per_host: Dict[str, float] = {}

    @contextmanager
    def __call__(self, prepared_req: PreparedRequest, log: LogEntry, courtesy_seconds: Optional[float] = None):
        if courtesy_seconds is None:
            courtesy_seconds = self.courtesy_seconds
        host = str(urlparse(prepared_req.url).hostname)
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
        if isinstance(cache, Path):
            cache = Cache(cache)
        self.cache = cache
        if not isinstance(courtesy_sleep, CourtesySleep):
            courtesy_sleep = CourtesySleep(courtesy_sleep)  # malkovitch malkovitch
        self.courtesy_sleep = courtesy_sleep
        self.session = session or Session()
        self.logger = self._init_logger(propagate_logs)

    def fetch(
        self,
        url: str,
        courtesy_seconds: Optional[float] = None,
        raise_for_status: bool = True,
        **kwargs,
    ) -> Response:
        frame = _SCRAPER_LOCAL.stack[-1]
        kwargs.update(frame.scraper_kwargs)
        frame.logger = self.logger
        force_cache_stale = kwargs.pop('force_cache_stale', False)
        prepared_req, request_kwargs = self._prepare(url, **kwargs)
        log = LogEntry(prepared_req)
        res = None
        if self.cache and not force_cache_stale:
            res = self.cache.get(prepared_req, log)
        if res is not None:
            self.session.cookies.extract_cookies(MockResponse(res), MockRequest(prepared_req))  # type: ignore
        else:
            with self.courtesy_sleep(prepared_req, log, courtesy_seconds):
                res = self.session.request(**request_kwargs)
            if self.cache:
                self.cache.put(prepared_req, res)
        self.logger.info('%s', log)
        if raise_for_status:
            res.raise_for_status()
        return res

    def _prepare(self, url: str, **kwargs) -> Tuple[PreparedRequest, Dict]:
        default_method = (
            'POST' if (kwargs.get('data') is not None or kwargs.get('files') is not None or kwargs.get('json') is not None)
            else 'GET'
        )
        method = kwargs.pop('method', default_method).upper()
        for arg in ('data', 'files'):
            if isinstance(kwargs.get(arg), dict):
                for key, value in list(kwargs[arg].items()):
                    # Read the files to memory. This is required because this request ends up being prepared twice, once by us and
                    # once by Requests. This is what requests.models.PreparedRequest.prepare_body does anyway
                    if callable(getattr(value, 'read', None)):
                        kwargs[arg][key] = value.read()
                        value.close()
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
        return prepared_req, {'url': url, 'method': method, **kwargs}

    def get(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='GET', **kwargs)

    def post(self, url: str, data=None, **kwargs) -> Response:
        return self.fetch(url, method='POST', data=data, **kwargs)

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


class MockResponse:

    def __init__(self, response: Response):
        self.response = response

    def info(self):
        return self

    def get_all(self, name, failobj=None):
        # This is a mock of `email.message.EmailMessage.get_all` -- ``Return a list of all the values for the field named name. If
        # there are no such named headers in the message, failobj is returned''
        #
        # See https://docs.python.org/3.8/library/email.message.html#email.message.EmailMessage.get_all
        if name in self.response.headers:
            return [self.response.headers[name]]
        return failobj


def scraper(
    no_parens_function: Optional[Callable] = None,
    *,
    retry_on: Tuple[type, ...] = (),
    num_attempts: int = 5,
):
    if no_parens_function:
        # decorator is without parentheses
        return scraper()(no_parens_function)

    @contextmanager
    def scraper_stack_frame():
        frame = ThreadLocalData()
        _SCRAPER_LOCAL.stack.append(frame)
        try:
            yield frame
        finally:
            _SCRAPER_LOCAL.stack.pop()

    retry_on = (ScraperError, *retry_on)

    def make_wrapper(function: Callable):
        @wraps(function)
        def wrapper(*args, **kwargs):
            with scraper_stack_frame() as frame:
                for attempt in range(num_attempts):
                    try:
                        if attempt > 0:
                            frame.scraper_kwargs['force_cache_stale'] = True
                        return function(*args, **kwargs)
                    except Exception as error:  # pylint: disable=broad-except
                        if isinstance(error, retry_on) and attempt < num_attempts - 1:
                            delay = 5 ** attempt
                            if frame.logger:
                                frame.logger.error('%s: %s - sleeping %ds', type(error).__name__, error, delay)
                            sleep(delay)
                        else:
                            raise
        return wrapper
    return make_wrapper
