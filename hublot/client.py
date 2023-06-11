#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from datetime import timedelta
from time import sleep, time
from typing import Dict, Iterator, Optional, Sequence
from urllib.parse import urljoin, urlparse

# 3rd parties
#
# Even when using other engines, we rely on requests's utilities for handling cookies here, otherwise we'd have several wheels to
# reinvent
from requests.cookies import RequestsCookieJar

# hublot
from .cache import CacheKey, CacheSpec, UserSpecifiedCacheKey, load_cache
from .compile import compile_request
from .config import Config
from .datastructures import CompiledRequest, Requestable, Response, TooManyRedirects, get_cookies_from_response
from .decorator import SCRAPER_LOCAL
from .engines import EngineSpec, load_engine_pool
from .logs import LOGGER, LogEntry


class HttpClient:
    """
    Core class for this package. Meant as a mostly-drop-in replacement for `requests.Session`, but handles caching, courtesy
    sleep, and can multiple engines for performing the actual HTTP transactions.
    """

    def __init__(
        self,
        cache: CacheSpec = None,
        engines: Sequence[EngineSpec] = ('requests',),
        **config_kwargs,
    ) -> None:
        self.config = Config(**config_kwargs)
        self.cache = load_cache(cache, self.config.max_cache_age)
        self.engines = load_engine_pool(engines)
        self.cookies = RequestsCookieJar()
        self.last_request_per_host: Dict[str, float] = {}

    def fetch(
        self,
        url: Requestable,
        cache_key: Optional[UserSpecifiedCacheKey] = None,
        **kwargs,
    ) -> Response:
        """
        Main public method for this class.

        NB the first parameter is called `url`, even though it could also be a `Request` object, simply because that's shorter
        and nicer than calling it `requestable`. Hey, `urllib.request.urlopen` does the same thing, so.
        """
        config, request_kwargs = self.config.derive_using_kwargs(**kwargs)
        history: list[Response] = []
        for redirect_count in range(config.max_redirects):
            res = self._fetch_without_redirect(
                url,
                cache_key,
                config,
                request_kwargs,
                is_redirect=(redirect_count > 0),
            )
            if config.allow_redirects and res.is_redirect:
                url = urljoin(res.url, res.headers['Location'])
                cache_key = cache_key and CacheKey.parse(cache_key).next_in_sequence()
                history.append(res)
            else:
                if config.raise_for_status:
                    res.raise_for_status()
                res.history = history
                return res
        raise TooManyRedirects(f'Exceeded {config.max_redirects} redirects')

    def _fetch_without_redirect(
        self,
        url: Requestable,
        cache_key: Optional[UserSpecifiedCacheKey],
        config: Config,
        request_kwargs: Dict[str, object],
        is_redirect: bool,
    ) -> Response:
        frame = SCRAPER_LOCAL.stack[-1]
        if frame.is_retry:
            config.force_cache_stale = True
            config.courtesy_sleep = timedelta(0)
        creq = compile_request(self.cookies, config, url, request_kwargs)
        log = LogEntry(creq, is_redirect)
        res = self._fetch_response(cache_key, config, creq, is_redirect, log)
        if config.cookies_enabled:
            get_cookies_from_response(self.cookies, res)
        LOGGER.info('%s', log)
        return res

    def _fetch_response(
        self,
        cache_key: Optional[UserSpecifiedCacheKey],
        config: Config,
        creq: CompiledRequest,
        is_redirect: bool,
        log: LogEntry,
    ) -> Response:
        """
        Either read the Response from cache, or perform the HTTP transaction and save the response to cache
        """
        if self.cache and not config.force_cache_stale:
            res = self.cache.get(creq, log, config.max_cache_age, cache_key)
            if res is not None:
                res.from_cache = True
                return res
        with self._sleep_if_needed(config, creq, is_redirect, log):
            res = self.engines.request(creq, config)
        assert not res.from_cache  # would be an engine bug
        if self.cache:
            self.cache.put(creq, log, res, cache_key)
        return res

    @contextmanager
    def _sleep_if_needed(
        self,
        config: Config,
        creq: CompiledRequest,
        is_redirect: bool,
        log: LogEntry,
    ) -> Iterator[None]:
        host = urlparse(creq.url).hostname or ''
        last_request = self.last_request_per_host.get(host, 0)
        if config.courtesy_sleep and not is_redirect:
            delay_seconds = (last_request + config.courtesy_sleep.total_seconds()) - time()
            if delay_seconds > 0:
                log.courtesy_seconds = delay_seconds
                sleep(delay_seconds)
        try:
            yield
        finally:
            # NB we store the time after the request is complete
            self.last_request_per_host[host] = time()

    ### for a thin veneer of Requests compatibility

    def request(self, method: str, url: str, **kwargs) -> Response:
        return self.fetch(url, method=method, **kwargs)

    def get(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='GET', **kwargs)

    def post(self, url: str, data=None, **kwargs) -> Response:
        return self.fetch(url, method='POST', data=data, **kwargs)
