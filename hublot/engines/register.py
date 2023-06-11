#!/usr/bin/env python3

# standards
from typing import Dict, Type

# hublot
from .base import Engine


ALL_ENGINES: Dict[str, Type[Engine]] = {}


def register_engine(engine_class: Type[Engine]) -> None:
    ALL_ENGINES[engine_class.id] = engine_class
