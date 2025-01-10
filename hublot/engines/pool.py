#!/usr/bin/env python3

# standards
from collections.abc import Sequence
from typing import Optional
from uuid import UUID

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, Response
from ..decorator import SCRAPER_LOCAL
from .base import Engine


class EnginePool(Engine):
    id = "engine-pool"

    def __init__(self, engines: Sequence[Engine]):
        self.engines = tuple(engines)
        self.rotation = 0
        self.last_state: tuple[Optional[UUID], int] = (None, 0)

    def _get_next_engine(self, save_state: bool = False) -> Engine:
        frame = SCRAPER_LOCAL.stack[-1]
        if frame.num_retries == 0:
            # This is our first attempt at this request, use which ever engine is at the front of the queue, and don't rotate. As
            # long as that engine works, we'll keep using it
            return self.engines[self.rotation]
        else:
            state = (frame.request_uuid, frame.num_retries)
            if self.last_state == state:
                # We've been called already for this attempt at performing this request. This happens because both `short_code` and
                # `request` call this function. Don't rotate, just return the same engine that we've already returned for this
                # attempt at performing this request.
                return self.engines[self.rotation]
            else:
                # We failed in our previous attempt at performing this request, and now we're attempting again. Rotate the engines.
                rotation = (self.rotation + 1) % len(self.engines)
                if save_state:
                    self.rotation = rotation
                    self.last_state = state
                return self.engines[rotation]

    def short_code(self) -> str:
        return self._get_next_engine().short_code()

    def request(self, creq: CompiledRequest, config: Config) -> Response:
        return self._get_next_engine(save_state=True).request(creq, config)
