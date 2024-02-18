#!/usr/bin/env python3

# standards
import logging
import re
import subprocess
from typing import Iterable, Optional, Tuple
from urllib.parse import urlparse

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, ConnectionError, Headers, Response, HublotException
from .base import Engine
from .pycurl import RE_HEADER, RE_STATUS
from .register import register_engine


LOGGER = logging.getLogger(__name__)


class CurlCmdEngineError(HublotException):
    """
    These exceptions indicate problems that are outside of HTTP errors -- unable to invoke the `curl` command, or to parse its
    output. This would be a bug or a system setup problem.
    """


class CurlCmdEngine(Engine):

    id = 'curlcmd'

    def __init__(self, curl_cmd: str = 'curl') -> None:
        self.curl_cmd = curl_cmd

    def short_code(self) -> str:
        return 'cc'

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        curl = subprocess.run(
            list(self._compose_curl_command(creq, config)),
            input=creq.data,
            capture_output=True,
            check=False,
        )
        if curl.returncode != 0:  # pragma: no cover
            output = curl.stderr.decode('UTF-8')
            message_match = re.search(fr'curl: \({curl.returncode}\) (.+)', output)
            message = message_match[1] if message_match else None
            if curl.returncode == 6:
                raise ConnectionError(message or output)
            else:
                raise HublotException(output)

        headers_match = re.search(br'\r?\n\r?\n', curl.stdout)
        if not headers_match:  # pragma: no cover
            raise Exception('Failed to find headers in curl output')
        headers_str = curl.stdout[: headers_match.start()].decode('ISO-8859-1')

        status_code, reason, headers_str = self._parse_status_line(headers_str)
        return Response(
            request=creq,
            from_cache=False,
            history=[],
            status_code=status_code,
            reason=reason,
            headers=self._parse_headers(headers_str),
            content=curl.stdout[headers_match.end() :],
        )

    def _compose_curl_command(self, creq: CompiledRequest, config: Config) -> Iterable[str]:
        yield from [
            self.curl_cmd,
            creq.url,
            '--request',
            creq.method,
            '--connect-timeout',
            str(config.timeout),
            '--compressed',
            '--include',
        ]
        for key, value in creq.headers.items():
            yield from ['-H', f'{key}: {value}']
        if creq.data is not None:
            yield from ['--data-binary', '@-']
        if config.proxies:
            scheme = urlparse(creq.url).scheme
            proxy = config.proxies.get(scheme)
            if proxy:
                yield from ['--proxy', proxy]
        if not config.verify:
            yield '--insecure'

    @staticmethod
    def _parse_status_line(headers_str: str) -> Tuple[int, Optional[str], str]:
        match = RE_STATUS.search(headers_str)
        if not match:  # pragma: no cover
            raise HublotException('Malformed headers')
        return int(match[1]), match[2], headers_str[match.end() :]

    @staticmethod
    def _parse_headers(headers_str: str) -> Headers:
        headers = Headers()
        for match in RE_HEADER.finditer(headers_str):
            headers.add(match[1], match[2])
        return headers


register_engine(CurlCmdEngine)
