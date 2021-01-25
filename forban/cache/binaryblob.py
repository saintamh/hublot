#!/usr/bin/env python3

"""
Functions for serialising request and response objects to binary blobs, which can then be stored in any storage.

The format used is designed to mimic the HTTP exchange that travels on the wire, i.e. the blob starts with a rendering of the HTTP
request head, then request body if present, then the response head, then body. This makes it convenient to inspect the blobs for
manual debugging.
"""

# standards
from codecs import getwriter
from io import BytesIO
import re
from typing import Callable, Optional, Tuple

# 3rd parties
from requests import PreparedRequest, Response
from requests.structures import CaseInsensitiveDict


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
    preq: PreparedRequest,
    output: BytesIO,
    write: Callable[[str], None],
) -> None:

    write(f'{preq.method} {preq.url}{EOL}')
    for key, value in sorted(preq.headers.items()):
        write(f'{key}: {value}{EOL}')
    write(EOL)
    content_length = int(preq.headers.get('Content-Length') or 0)
    if preq.body is not None:
        if content_length != len(preq.body):
            # Don't write it out because we won't be able to read it back
            raise Exception(f'body has {len(preq.body)} bytes but Content-Length is {content_length}')
        if isinstance(preq.body, str):
            # `PreparedRequest.prepare_body` leaves `body` as a `str` if `data` was a dict
            body_bytes = preq.body.encode('UTF-8')
        else:
            body_bytes = preq.body
        output.write(body_bytes)
        write(EOL)
    else:
        if content_length > 0:
            # Again, need to make sure Content-Length can reliably be used for parsing later
            raise Exception(f'body is None but Content-Length is {content_length}')


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
    # pylint: disable=protected-access
    pos = 0
    _method_unused, url, pos = _parse_line(data, pos, r'^(\w+) (.+)$')
    _headers_unused, _body_unused, pos = _parse_message(data, pos)
    status_code, reason, pos = _parse_line(data, pos, r'^HTTP (\d+) (.+)$')
    res = Response()
    res.status_code = int(status_code)
    res.reason = reason
    res.url = url
    res.headers, res._content, pos = _parse_message(data, pos, read_to_end=True)
    res._content_consumed = True  # type: ignore
    return res


def _parse_message(
    data: bytes,
    pos: int,
    read_to_end: bool = False,
) -> Tuple[CaseInsensitiveDict, Optional[bytes], int]:

    headers: CaseInsensitiveDict = CaseInsensitiveDict()
    while data[pos : pos+EOL_LEN] != EOL_BYTES:
        key, value, pos = _parse_line(data, pos, r'^([^:]+): (.+)$')
        headers[key] = value
    pos += EOL_LEN
    body: Optional[bytes] = None
    if read_to_end:
        body = data[pos : ]
        pos = len(data)
    elif headers.get('Content-Length'):
        length = int(headers['Content-Length'])
        body = data[pos : pos+length]
        pos += length + EOL_LEN
    return headers, body, pos


def _parse_line(data: bytes, pos: int, regex: str):
    eol_pos = data.find(EOL_BYTES, pos)
    line = data[pos : eol_pos].decode('UTF-8')
    match = re.search(regex, line)
    if not match:
        raise ValueError(repr(line))
    return (*match.groups(), eol_pos + EOL_LEN)
