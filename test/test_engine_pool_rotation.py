#!/usr/bin/env python3

# standards
import re

# hublot
from hublot import HttpClient, retry_on_scraper_error
from hublot.config import Config
from hublot.datastructures import CompiledRequest, ConnectionError, Headers, Response
from hublot.engines import Engine, register_engine


class TestEngine(Engine):

    def short_code(self) -> str:
        return self.id[-1:]

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        return Response(
            request=creq,
            from_cache=False,
            history=[],
            status_code=200,
            reason="OK",
            headers=Headers(),
            content=f"/{re.sub(r'.+/', '', creq.url)} from {self.id}".encode("UTF-8"),
        )


class Engine1(TestEngine):
    id = "engine1"

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        if creq.url.endswith("/3"):
            raise ConnectionError("boom")  # network error
        return super().request(creq, config)


class Engine2(TestEngine):
    id = "engine2"

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        if creq.url.endswith("/6"):
            return Response(
                request=creq,
                from_cache=False,
                history=[],
                status_code=404,  # HTTP status error
                reason="Not Found",
                headers=Headers(),
                content=b"Not Found",
            )
        return super().request(creq, config)


class Engine3(TestEngine):
    id = "engine3"

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        if creq.url.endswith("/9"):
            return Response(
                request=creq,
                from_cache=False,
                history=[],
                status_code=200,
                reason="OK",
                headers=Headers(),
                content=b"Not the data you expected",
            )
        return super().request(creq, config)


def test_engine_pool_rotation_on_network_error() -> None:
    register_engine(Engine1)
    register_engine(Engine2)
    register_engine(Engine3)

    client = HttpClient(
        engines=[
            "engine1",
            "engine2",
            "engine3",
        ],
    )

    @retry_on_scraper_error
    def fetch(i) -> str:
        return parse(client.get(f"http://hublot.test/{i}").text)

    def parse(text: str) -> str:
        if " from " not in text:
            raise ValueError(text)
        return text

    results = list(map(fetch, range(12)))
    assert results == [
        "/0 from engine1",
        "/1 from engine1",
        "/2 from engine1",
        # engine1 gives a network error on /3, we're on to engine2
        "/3 from engine2",
        "/4 from engine2",
        "/5 from engine2",
        # engine2 returned an HTTP error on /6, we're on to engine3
        "/6 from engine3",
        "/7 from engine3",
        "/8 from engine3",
        # engine3 triggered a ValueError, we're back at engine1
        "/9 from engine1",
        "/10 from engine1",
        "/11 from engine1",
    ]
