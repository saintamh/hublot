#!/usr/bin/env python3

# standards
import json
from typing import Optional
from urllib.parse import urlencode

# 3rd parties
from requests.cookies import RequestsCookieJar, get_cookie_header

# hublot
from .config import Config
from .datastructures import CompiledRequest, Headers, Request


def compile_request(
    req: Request,
    config: Config,
    cookies: RequestsCookieJar,
    num_retries: int,
) -> CompiledRequest:
    headers = _compile_request_headers(config, req)
    data = _compile_request_data(req, headers)
    creq = CompiledRequest(
        url=_compile_request_url(req),
        method=req.method.upper() if req.method else ("POST" if data is not None else "GET"),
        headers=headers,
        data=data,
        num_retries=num_retries,
    )
    _add_cookies_to_request(req, cookies, creq)
    return creq


def _compile_request_headers(config: Config, req: Request) -> Headers:
    headers = Headers()
    if config.headers:
        headers.add_all(config.headers)
    if req.headers:
        headers.add_all(req.headers)
    headers.setdefault("Accept", "*/*")
    if config.user_agent:
        headers.setdefault("User-Agent", config.user_agent)
    return headers


def _compile_request_url(req: Request) -> str:
    if not req.params:
        return req.url
    url = req.url.rstrip("?&")
    return (
        url
        + ("&" if "?" in url else "?")
        # We unconditionally use UTF-8 to encode URL params. In cases where this isn't desirable, the client should urlencode the
        # params itself, and pass them in str form, as part of the `url`.
        + urlencode(req.params, encoding="UTF-8")
    )


def _compile_request_data(req: Request, headers: Headers) -> Optional[bytes]:
    data = req.data
    if data is not None and req.json is not None:
        raise TypeError("Request cannot have both `data` and `json` set")
    if req.json is not None:
        headers.setdefault("Content-Type", "application/json")
        data = json.dumps(req.json, separators=(",", ":"))
    elif data is not None and not isinstance(data, (str, bytes)):
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        data = urlencode(data)
    if data is not None:
        if not isinstance(data, bytes):
            # We always encode as UTF-8. If another encoding is desired, the data should be pre-compiled to bytes by the caller
            data = data.encode("UTF-8")
        # We set a default content-type when uploading data. This is what Curl does, in fact I couldn't find a way of disabling
        # that.
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    if data is not None or (req.method and req.method.upper() not in ("HEAD", "GET")):
        # We set a Content-Length header even if `data` is None. This is what Requests does (in `prepare_content_length`), so for
        # consistency across engines we do the same.
        headers.setdefault("Content-Length", str(len(data or b"")))
    return data


def _add_cookies_to_request(
    req: Request,
    cookies: RequestsCookieJar,
    creq: CompiledRequest,
) -> None:
    """
    `req` is the user-supplied request, which may contain hard-coded cookies
    `cookies` is the `HttpClient`'s cookie jar, containing accumulated cookies from previous requests
    """
    if req.cookies:
        # If `Request.cookies` are set, they override any accumulated cookies
        cookies = cookies.copy()
        for key, value in req.cookies.items():
            cookies[key] = value
    cookie_header = get_cookie_header(cookies, creq)
    if cookie_header is not None:
        creq.headers.add("Cookie", cookie_header)
