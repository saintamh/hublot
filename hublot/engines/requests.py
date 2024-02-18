#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from http.cookiejar import DefaultCookiePolicy
import re
from typing import Set

# 3rd parties
import requests
import urllib3.util.url

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, ConnectionError, Headers, HublotException, Response
from .base import Engine
from .register import register_engine


class RequestsEngine(Engine):

    id = 'requests'

    def __init__(self) -> None:
        self.session = requests.Session()
        # let hublot.HttpClient manage cookies
        self.session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))

    def short_code(self) -> str:
        return 'rq'

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        try:
            with patched_encode_invalid_chars():
                rres = self.session.request(
                    url=creq.url,
                    method=creq.method,
                    headers=creq.headers,  # type: ignore  # it fits in a duck-typed way
                    data=creq.data,
                    verify=config.verify,
                    allow_redirects=False,
                    timeout=config.timeout,
                )
                return Response(
                    request=creq,
                    from_cache=False,
                    history=[],
                    status_code=rres.status_code,
                    reason=rres.reason,
                    headers=Headers(rres.raw._fp.headers),  # pylint: disable=protected-access
                    content=rres.content,
                )
        except requests.exceptions.ConnectionError as error:
            raise ConnectionError(error) from error
        except requests.exceptions.RequestException as error:
            raise HublotException(error) from error


_encode_invalid_chars = urllib3.util.url._encode_invalid_chars  # type: ignore  # pylint: disable=protected-access


def _encode_invalid_chars_preserve_case(component: str, *rest, **kwargs) -> str:
    new = _encode_invalid_chars(component, *rest, **kwargs)
    if new != component:
        # `urllib3`, which is used internally by `requests`, changes the casing of %xx escapes, always forcing them to uppercase.
        # This means that if a server is set up such that when you ask for a URL with uppercase escapes it redirects you to the
        # same URL with lowercase escapes, then `requests` is unable to fetch that page -- the URL in the redirect response
        # 'location' will be re-uppercased, leading to a redirect loop. Here we work around that by chaging it back to lowercase.
        #
        # You could argue that the HTTP spec says %-escapes are case-insensitive, so it's the server described above that's
        # buggy, but browsers have no problem fetching such a page, so I'd argue it's a `requests` bug.
        #
        new = re.sub(r'%[0-9a-fA-F]{2}', lambda m: m.group().lower(), new)
    return new


@contextmanager
def patched_encode_invalid_chars():
    # pylint: disable=protected-access
    original = urllib3.util.url._encode_invalid_chars
    urllib3.util.url._encode_invalid_chars = _encode_invalid_chars_preserve_case
    try:
        yield
    finally:
        urllib3.util.url._encode_invalid_chars = original


register_engine(RequestsEngine)
