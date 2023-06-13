#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from http.cookiejar import DefaultCookiePolicy
import re
from typing import Set, Union

# 3rd parties
import requests
import urllib3.util.url

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, Headers, HublotException, Response
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
                    reason=_decode_reason(rres.reason),
                    headers=Headers(rres.raw._fp.headers),  # pylint: disable=protected-access
                    content=rres.content,
                )
        except requests.exceptions.RequestException as error:
            raise HublotException(error) from error


def _decode_reason(reason: Union[str, bytes]) -> str:
    if isinstance(reason, bytes):
        # Code and comment copied from `requests.models`:
        #
        #     We attempt to decode utf-8 first because some servers choose to localize their reason strings. If the string isn't
        #     utf-8, we fall back to iso-8859-1 for all other encodings. (See PR #3538)
        try:
            return reason.decode('UTF-8')
        except UnicodeDecodeError:
            return reason.decode('ISO-8859-1')
    else:
        return reason



_encode_invalid_chars = urllib3.util.url._encode_invalid_chars  # type: ignore  # pylint: disable=protected-access


def _encode_invalid_chars_preserve_case(component: str, allowed_chars: Set[str], encoding: str = 'utf-8') -> str:
    new = _encode_invalid_chars(component, allowed_chars, encoding=encoding)
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
