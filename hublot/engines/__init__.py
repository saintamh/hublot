#!/usr/bin/env python3

# standards
from typing import List, Literal, Sequence, Type, Union

# hublot
from .base import Engine
from .curlcmd import CurlCmdEngine
from .pool import EnginePool
from .pycurl import PyCurlEngine
from .register import ALL_ENGINES, register_engine
from .requests import RequestsEngine


EngineSpec = Union[Engine, str]


def load_engine_pool(engine_specs: Sequence[EngineSpec]) -> EnginePool:
    return EnginePool(
        engines=list(map(_get_engine_instance, engine_specs)),
    )


def _get_engine_instance(spec: EngineSpec) -> Engine:
    if isinstance(spec, Engine):
        return spec
    if ':' in spec:
        # You can pass string args to the Engine constructor by putting then after a colon. At the moment only the CurlCmdEngine
        # uses that. If an engine needs more complex constructor args, the client code can just instantiate the engine class
        # itself. This is just a minor convenience to avoid the client having to import the CurlCmdEngine class.
        engine_id, *engine_args = spec.split(':')
    else:
        engine_id = spec
        engine_args = []
    engine_class = ALL_ENGINES[engine_id]
    return engine_class(*engine_args)
