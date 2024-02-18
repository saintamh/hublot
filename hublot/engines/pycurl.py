#!/usr/bin/env python3

# standards
from io import BytesIO
import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

# 3rd parties
try:
    import pycurl

    HAVE_PYCURL = True
except ImportError:
    HAVE_PYCURL = False

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, ConnectionError, Headers, HublotException, Response
from .base import Engine
from .register import register_engine


LOGGER = logging.getLogger(__name__)


RE_STATUS = re.compile(
    r"^\s* HTTP/\d+(?:\.\d+)? \s+ (\d\d\d) \s* (?: (\S.+?) \s* )? $",
    flags=re.M | re.X,
)

RE_HEADER = re.compile(
    r"^\s* ([^:]+?) \s*:\s* (.+?) \s*$",
    flags=re.M | re.X,
)


class PyCurlEngine(Engine):

    id = "pycurl"

    def __init__(self) -> None:
        if not HAVE_PYCURL:
            raise ImportError("pycurl is not installed; maybe try 'pip install hublot[pycurl]'")
        self.curl: Any = pycurl.Curl()  # pylint: disable=c-extension-no-member

    def short_code(self) -> str:
        return "pc"

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        c = self.curl

        c.setopt(c.URL, creq.url)
        c.setopt(c.CUSTOMREQUEST, creq.method)
        c.setopt(
            c.HTTPHEADER,
            [f"{key}: {value}".encode("ISO-8859-1") for key, value in creq.headers.items()],
        )
        if creq.data is not None:
            c.setopt(c.POSTFIELDS, creq.data)

        if config.proxies:
            scheme = urlparse(creq.url).scheme
            proxy = config.proxies.get(scheme)
            if proxy:
                c.setopt(c.PROXY, proxy)

        c.setopt(c.ACCEPT_ENCODING, "")  # accept all curl-supported encodings
        c.setopt(c.TIMEOUT, config.timeout)
        c.setopt(c.SSL_VERIFYHOST, 2 if config.verify else 0)
        c.setopt(c.SSL_VERIFYPEER, 1 if config.verify else 0)

        headers = Headers()
        status_code: list[int] = []
        reason: list[Optional[str]] = []

        c.setopt(c.HEADERFUNCTION, lambda line: self.handle_header_line(headers, status_code, reason, line))
        output_bytes = BytesIO()
        c.setopt(c.WRITEFUNCTION, output_bytes.write)
        try:
            c.perform()
        except pycurl.error as error:  # pylint: disable=c-extension-no-member
            error_code, message = error.args
            if error_code == 6:
                raise ConnectionError(message) from error
            else:
                raise HublotException() from error

        return Response(
            request=creq,
            from_cache=False,
            history=[],
            status_code=status_code[0],
            reason=reason[0] if reason else None,
            headers=headers,
            content=output_bytes.getvalue(),
        )

    @staticmethod
    def handle_header_line(
        headers: Headers,
        status_code: list[int],
        reason: list[Optional[str]],
        line_bytes: bytes,
    ) -> None:
        # HTTP standard specifies that headers are encoded in iso-8859-1
        line = line_bytes.decode("ISO-8859-1")
        if not line.strip():
            return
        if not status_code:
            match = RE_STATUS.match(line)
            if match:
                status_code.append(int(match[1]))
                reason.append(match[2])
            else:  # pragma: no cover
                LOGGER.warning("Malformed status line: %r", line)
        else:
            match = RE_HEADER.match(line)
            if match:
                headers.add(match[1], match[2])
            else:  # pragma: no cover
                LOGGER.warning("Malformed header line: %r", line)


register_engine(PyCurlEngine)
