#!/usr/bin/env python3

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, Response
from .base import Engine


class EnginePool(Engine):

    id = "engine-pool"

    def __init__(self, engines: list[Engine]):
        self.engines = engines

    def short_code(self) -> str:
        return self.engines[0].short_code()

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        engine_idx = creq.num_retries % len(self.engines)
        res = self.engines[0].request(creq, config)
        if engine_idx > 0:
            # After we've found a working engine, move it to the front of the list, so that subsequent attempts will use it. This
            # is an inefficient operation, but the list is only ever going to have 1 to 3 items, and this operation isn't expected
            # to happen a lot anyway
            self.engines = self.engines[engine_idx:] + self.engines[:engine_idx]
        return res
