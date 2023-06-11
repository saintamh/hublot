#!/usr/bin/env python3

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, HublotException, Response
from .base import Engine


class EnginePool(Engine):

    id = 'engine-pool'

    def __init__(self, engines: list[Engine]):
        self.engines = engines

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        try:
            return self.engines[0].request(creq, config)
        except HublotException:
            if len(self.engines) > 1:
                # Rotate the engine list, so that the next attempt will be with the next engine. This is an inefficient operation,
                # but the list is only ever going to have 1 to 3 items, and this operation isn't expected to happen a lot anyway
                self.engines = self.engines[1:] + self.engines[:1]
            raise
