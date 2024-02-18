#!/usr/bin/env python3

"""
Functions for serialising request and response objects to binary blobs, which can then be stored in any storage.

The format used is designed to mimic the HTTP exchange that travels on the wire, i.e. the blob starts with an loose rendering of
the HTTP request head, then request body if present, then the response head, then body. This makes it convenient to inspect the
blobs for manual debugging.
"""

# standards
from codecs import getwriter
from io import BytesIO
import re
from typing import Callable, Optional, Tuple

# hublot
from ..datastructures import CompiledRequest, Headers, Response


EOL = '\r\n'
EOL_BYTES = EOL.encode('UTF-8')
EOL_LEN = len(EOL)


Writer = getwriter('UTF-8')  # pylint: disable=invalid-name


def compose_binary_blob(res: Response) -> bytes:
    output = BytesIO()
    write = Writer(output).write
    _compose_request_blob(res.request, output, write)
    _compose_response_blob(res, output, write)
    return output.getvalue()


def _compose_request_blob(
    creq: CompiledRequest,
    output: BytesIO,
    write: Callable[[str], None],
) -> None:
    write(f'{creq.method} {creq.url}{EOL}')
    for key, value in sorted(creq.headers.items()):
        write(f'{key}: {value}{EOL}')
    write(EOL)
    if 'Content-Length' in creq.headers:
        body = b'' if creq.data is None else creq.data
        content_length = int(creq.headers['Content-Length'])
        if content_length != len(body):
            # Don't write it out because we won't be able to read it back
            raise Exception(f'body has {len(body)} bytes but Content-Length is {content_length}')
        output.write(body)
        write(EOL)
    else:
        assert creq.data is None, "compile_request should've set the Content-Length"
    write(EOL)


def _compose_response_blob(
    res: Response,
    output: BytesIO,
    write: Callable[[str], None],
) -> None:
    write(f'HTTP {res.status_code} {res.reason}{EOL}')
    for key, value in sorted(res.headers.items()):
        write(f'{key}: {value}{EOL}')
    write(EOL)
    if res.content is not None:
        output.write(res.content)


def parse_binary_blob(data: bytes) -> Response:
    pos = 0
    method, url, pos = _parse_line(data, pos, r'^(\w+) (.+)$')
    req_headers, req_body, pos = _parse_message(data, pos)
    creq = CompiledRequest(
        url=url,
        method=method,
        headers=req_headers,
        data=req_body,
        num_retries=0,
    )
    status_code, reason, pos = _parse_line(data, pos, r'^HTTP (\d+) (.*)$')
    res_headers, res_body, pos = _parse_message(data, pos, read_to_end=True)
    assert res_body is not None  # since we passed `read_to_end=True`
    return Response(
        request=creq,
        from_cache=True,
        history=[],  # set elsewhere
        status_code=int(status_code),
        reason=reason,
        headers=res_headers,
        content=res_body,
    )


def _parse_message(
    data: bytes,
    pos: int,
    read_to_end: bool = False,
) -> Tuple[Headers, Optional[bytes], int]:
    headers = Headers()
    while data[pos : pos + EOL_LEN] != EOL_BYTES:
        key, value, pos = _parse_line(data, pos, r'^([^:]+): (.*)$')
        headers[key] = value
    pos += EOL_LEN
    body: Optional[bytes] = None
    if read_to_end:
        body = data[pos:]
        pos = len(data)
    elif headers.get('Content-Length'):
        length = int(headers['Content-Length'])
        body = data[pos : pos + length]
        pos += length + (2 * EOL_LEN)
    else:
        pos += EOL_LEN
    return headers, body, pos


def _parse_line(data: bytes, pos: int, regex: str):
    eol_pos = data.find(EOL_BYTES, pos)
    line = data[pos:eol_pos].decode('UTF-8')
    match = re.search(regex, line)
    if not match:  # pragma: no cover
        raise ValueError(repr(line))
    return (*match.groups(), eol_pos + EOL_LEN)
