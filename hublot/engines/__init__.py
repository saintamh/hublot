#!/usr/bin/env python3

# standards
from typing import List, Literal, Sequence, Type, Union

# hublot
from .base import Engine
from .pool import EnginePool
from .register import ALL_ENGINES, register_engine
from .requests import RequestsEngine


EngineSpec = Union[Engine, Literal['requests']]


def load_engine_pool(engine_specs: Sequence[EngineSpec]) -> EnginePool:
    return EnginePool(
        engines=[
            engine if isinstance(engine, Engine) else ALL_ENGINES[engine]()
            for engine in engine_specs
        ],
    )
