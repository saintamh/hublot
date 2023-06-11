#!/usr/bin/env python3

# standards
import json
from typing import Dict, Optional
from urllib.parse import urlencode

# 3rd parties
from requests.cookies import RequestsCookieJar, get_cookie_header

# hublot
from .config import Config
from .datastructures import CompiledRequest, Headers, Request, Requestable


def compile_request(
    cookies: RequestsCookieJar,
    config: Config,
    url: Requestable,
    request_kwargs: Dict[str, object],
) -> CompiledRequest:
    req = _compile_user_request(url, request_kwargs)
    headers = _compile_request_headers(config, req)
    data = _compile_request_data(req, headers)
    creq = CompiledRequest(
        url=_compile_request_url(req),
        method=req.method.upper() if req.method else ('POST' if data is not None else 'GET'),
        headers=headers,
        data=data,
    )
    _add_cookies_to_request(cookies, creq)
    return creq


def _compile_user_request(url: Requestable, request_kwargs: Dict[str, object]) -> Request:
    """
    Take whatever the user passed to `fetch`, and make a `Request` object out of it.
    """
    if isinstance(url, Request):
        return url.replace(**request_kwargs)
    else:
        return Request(url=url, **request_kwargs)  # type: ignore  # let it throw TypeError if needed


def _compile_request_headers(config: Config, req: Request) -> Headers:
    headers = Headers(req.headers)
    headers.setdefault('Accept', '*/*')
    if config.user_agent:
        headers.setdefault('User-Agent', config.user_agent)
    return headers


def _compile_request_url(req: Request) -> str:
    if not req.params:
        return req.url
    url = req.url.rstrip('?&')
    return (
        url
        + ('&' if '?' in url else '?')
        # We unconditionally use UTF-8 to encode URL params. In cases where this isn't desirable, the client should urlencode the
        # params itself, and pass them in str form, as part of the `url`.
        + urlencode(req.params, encoding='UTF-8')
    )


def _compile_request_data(req: Request, headers: Headers) -> Optional[bytes]:
    data = req.data
    if data is not None and req.json is not None:
        raise TypeError('Request cannot have both `data` and `json` set')
    if req.json is not None:
        headers.setdefault('Content-Type', 'application/json')
        data = json.dumps(req.json)
    elif data is not None and not isinstance(data, (str, bytes)):
        headers.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        data = urlencode(data)
    if data is not None:
        if not isinstance(data, bytes):
            # We always encode as UTF-8. If another encoding is desired, the data should be pre-compiled to bytes by the caller
            data = data.encode('UTF-8')
        headers.setdefault('Content-Length', str(len(data)))
    return data


def _add_cookies_to_request(cookies: RequestsCookieJar, creq: CompiledRequest) -> None:
    cookie = get_cookie_header(cookies, creq)
    if cookie is not None:
        creq.headers.add('Cookie', cookie)
