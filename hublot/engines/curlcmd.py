#!/usr/bin/env python3

# standards
import logging
import re
import subprocess
from typing import Iterable, Optional, Tuple
from urllib.parse import urlparse

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, Headers, Response, HublotException
from .base import Engine
from .pycurl import RE_HEADER, RE_STATUS
from .register import register_engine


LOGGER = logging.getLogger(__name__)


class CurlCmdEngine(Engine):

    id = 'curlcmd'

    def short_code(self) -> str:
        return 'cc'

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        curl = subprocess.run(
            list(self._compose_curl_command(creq, config)),
            input=creq.data,
            capture_output=True,
            check=False,
        )
        if curl.returncode != 0:
            raise HublotException('curl: ' + curl.stderr.decode('UTF-8'))

        headers_match = re.search(br'\r?\n\r?\n', curl.stdout)
        if not headers_match:
            raise Exception('Failed to find headers in curl output')
        headers_str = curl.stdout[:headers_match.start()].decode('ISO-8859-1')

        status_code, reason, headers_str = self._parse_status_line(headers_str)
        return Response(
            request=creq,
            from_cache=False,
            history=[],
            status_code=status_code,
            reason=reason,
            headers=self._parse_headers(headers_str),
            content=curl.stdout[headers_match.end():],
        )

    @staticmethod
    def _compose_curl_command(creq: CompiledRequest, config: Config) -> Iterable[str]:
        yield from [
            'curl',
            creq.url,
            '--request', creq.method,
            '--connect-timeout', str(config.timeout),
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
        if not match:
            raise HublotException('Malformed headers')
        return int(match[1]), match[2], headers_str[match.end():]

    @staticmethod
    def _parse_headers(headers_str: str) -> Headers:
        headers = Headers()
        for match in RE_HEADER.finditer(headers_str):
            headers.add(match[1], match[2])
        return headers


register_engine(CurlCmdEngine)
