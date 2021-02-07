#!/usr/bin/env python3

# standards
from datetime import timedelta
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urljoin

# 3rd parties
from requests import PreparedRequest, Request, Response, Session, TooManyRedirects
from requests.cookies import MockRequest
from requests.structures import CaseInsensitiveDict

# forban
from .cache import Cache, CacheKey, UserSpecifiedCacheKey
from .courtesy import CourtesySleep
from .decorator import SCRAPER_LOCAL
from .logs import LOGGER, LogEntry
from .utils import ForbanCookiePolicy
from .version import FORBAN_VERSION


MAX_REDIRECTS = 10


class Client:

    def __init__(
        self,
        cache: Optional[Union[Cache, Path, str]] = None,
        courtesy_sleep: Optional[Union[CourtesySleep, float, timedelta]] = 5,
        session: Optional[Session] = None,
        max_cache_age: Optional[timedelta] = None,
        user_agent: str = f'forban/{FORBAN_VERSION}',
        cookies_enabled: bool = True,
    ):
        self.cache = Cache.load(cache, max_cache_age)
        if not isinstance(courtesy_sleep, CourtesySleep):
            courtesy_sleep = CourtesySleep(courtesy_sleep)  # malkovitch malkovitch
        self.courtesy_sleep = courtesy_sleep
        self.session = session or Session()
        self.session.cookies.set_policy(ForbanCookiePolicy(cookies_enabled))
        self.user_agent = user_agent

    @property
    def cookies(self):
        return self.session.cookies

    def fetch(
        self,
        url: str,
        method: Optional[str] = None,
        courtesy_seconds: Optional[float] = None,
        raise_for_status: bool = True,
        force_cache_stale: bool = False,
        allow_redirects: bool = True,
        cache_key: Optional[UserSpecifiedCacheKey] = None,
        max_cache_age: Optional[timedelta] = None,
        _redirected_from: Optional[Response] = None,
        **request_contents,
    ) -> Response:
        frame = SCRAPER_LOCAL.stack[-1]
        if frame.is_retry:
            force_cache_stale = True
            courtesy_seconds = 0
        preq = self._prepare(url, method, request_contents)
        log = LogEntry(preq, is_redirect=(_redirected_from is not None))
        res = None
        if self.cache and not force_cache_stale:
            res = self.cache.get(preq, log, cache_key, max_cache_age)
        if res is not None:
            for r in res.history + [res]:
                self.session.cookies.extract_cookies(MockResponse(r), MockRequest(preq))  # type: ignore
        else:
            with self.courtesy_sleep(preq, log, courtesy_seconds):
                res = self.session.request(
                    preq.method,  # type: ignore
                    url,
                    allow_redirects=False,
                    **request_contents
                )
            if self.cache:
                self.cache.put(preq, log, res, cache_key)
        if _redirected_from:
            res.history = [*_redirected_from.history, _redirected_from]
        LOGGER.info('%s', log)
        if allow_redirects and res.is_redirect:
            if _redirected_from and len(_redirected_from.history) >= MAX_REDIRECTS:
                raise TooManyRedirects(f'Exceeded {MAX_REDIRECTS} redirects')
            return self.fetch(
                urljoin(url, res.headers['Location']),
                courtesy_seconds=0,
                raise_for_status=raise_for_status,
                force_cache_stale=force_cache_stale,
                cache_key=cache_key and CacheKey.parse(cache_key).next_in_sequence(),
                _redirected_from=res,
            )
        if raise_for_status:
            res.raise_for_status()
        return res

    def _prepare(self, url: str, method: Optional[str], request_contents) -> PreparedRequest:
        """
        Given the user-supplied arguments to the `request`, method, compile a `PreparedRequest` object. Normally this is done
        within Requests (and it will still be done by Requests when we call it), but we need this in order to compute the cache
        key.
        """
        if method:
            method = method.upper()
        else:
            method = (
                'POST' if (
                    request_contents.get('data') is not None
                    or request_contents.get('files') is not None
                    or request_contents.get('json') is not None
                )
                else 'GET'
            )
        for arg in ('data', 'files'):
            if isinstance(request_contents.get(arg), dict):
                for key, value in list(request_contents[arg].items()):
                    # Read the files to memory. This is required because this request ends up being prepared twice, once by us and
                    # once by Requests. This is what requests.models.PreparedRequest.prepare_body does anyway
                    if callable(getattr(value, 'read', None)):
                        request_contents[arg][key] = value.read()
                        value.close()
        request_contents.setdefault('headers', CaseInsensitiveDict()).setdefault('User-Agent', self.user_agent)
        req = Request(url=url, method=method, **request_contents)
        return self.session.prepare_request(req)

    ### for a thin layer of Requests compatility

    def request(self, method: str, url: str, **kwargs) -> Response:
        return self.fetch(url, method, **kwargs)

    def get(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='GET', **kwargs)

    def post(self, url: str, data=None, **kwargs) -> Response:
        return self.fetch(url, method='POST', data=data, **kwargs)


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
        if callable(getattr(self.response.headers, 'get_all', None)):
            # It must be that `headers` is a `MultipleCaseInsensitiveDict` that we created when loading from cache. It gives us the
            # un-joined cookies, use that
            return self.response.headers.get_all(name, failobj)
        else:
            # Fall back to reading from the ', '-joined string.
            if name in self.response.headers:
                return [self.response.headers[name]]
        return failobj
