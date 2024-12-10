#!/usr/bin/env python3

# srandards
from inspect import cleandoc
import subprocess

# 3rd parties
import pytest

# hublot
from hublot import Headers, HttpClient, Request, Response
from hublot.compile import compile_request


@pytest.mark.parametrize(
    "curl_output, get_expected_response",
    [
        pytest.param(
            """
            HTTP/2 200 
            Content-Type: text/plain; charset=UTF-8
            Content-Length: 2
            
            OK
            """,
            lambda creq: Response(
                creq,
                from_cache=False,
                history=[],
                status_code=200,
                reason=None,
                headers=Headers(
                    {
                        "Content-Type": "text/plain; charset=UTF-8",
                        "Content-Length": "2",
                    }
                ),
                content=b"OK",
            ),
            id="simple 200 response",
        ),
        pytest.param(
            """
            HTTP/1.1 101 Switching Protocols
            Connection: Upgrade
            Upgrade: h2c

            HTTP/2 200 
            Content-Type: text/plain; charset=UTF-8
            Content-Length: 2

            OK
            """,
            lambda creq: Response(
                creq,
                from_cache=False,
                history=[],
                status_code=200,
                reason=None,
                headers=Headers(
                    {
                        "Content-Type": "text/plain; charset=UTF-8",
                        "Content-Length": "2",
                    }
                ),
                content=b"OK",
            ),
            id="101+200 double-response",
        ),
    ],
)
def test_engine_curlcmd(mocker, curl_output, get_expected_response):
    client = HttpClient(engines=["curlcmd"])
    mocker.patch(
        "hublot.engines.curlcmd.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=cleandoc(curl_output).replace("\n", "\r\n").encode("UTF-8"),
        ),
    )
    req = Request("http://test.test/", method="GET")
    creq = compile_request(req, client.config, client.cookies, num_retries=0)
    res = client.fetch(req)
    assert res == get_expected_response(creq)
