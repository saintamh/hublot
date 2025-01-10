#!/usr/bin/env python3

# standards
from collections.abc import Iterator
from dataclasses import dataclass
import logging
from typing import List, Optional, Union

# hublot
from .datastructures import CompiledRequest

LOGGER = logging.getLogger("hublot")


@dataclass(frozen=False)
class LogEntry:
    creq: CompiledRequest
    is_redirect: bool = False
    cache_key_str: Optional[str] = None
    cached: Optional[bool] = None
    courtesy_seconds: Optional[float] = None
    engine_short_code: Optional[str] = None

    def _compose_line(self) -> Iterator[str]:
        if self.cache_key_str:
            yield f"[{self.cache_key_str}] "
        if self.cached:
            yield "[cached] "
        else:
            engine_and_sleep = self._compose_engine_and_sleep()
            if engine_and_sleep:
                yield f"{engine_and_sleep:8s} "
            else:
                yield "         "
        if self.is_redirect:
            yield "-> "
        yield self.creq.url
        if self.creq.data is not None:
            yield f" [{self.creq.method} {len(self.creq.data)} bytes]"

    def _compose_engine_and_sleep(self) -> Optional[str]:
        if self.cached:
            return "[cached]"
        parts: List[str] = []
        if self.engine_short_code:
            parts.append(self.engine_short_code)
        if self.courtesy_seconds and self.courtesy_seconds > 0.5:
            parts.append(f"{round(self.courtesy_seconds)}s")
        if not parts:
            return None
        return "[%s]" % "+".join(parts)  # noqa: UP031

    def __str__(self) -> str:
        return "".join(self._compose_line())


def basic_logging_config(level: Union[int, str] = "INFO", propagate: bool = False) -> None:
    """
    Sets up logging for the common use case. Calls `logging.basicConfig`, lowers verbosity for the `urllib3` logger. If `propagate`
    is False (the default), a new handler will be attached to `hublot.LOGGER` that logs in a simple format to stderr, and does not
    propagate log events to the root logger.
    """
    if not isinstance(level, int):
        level = getattr(logging, level)
    logging.basicConfig(level=level)
    logging.getLogger("urllib3").setLevel(max(logging.WARNING, level))
    if not propagate and not LOGGER.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s", None, "%")
        handler.setFormatter(formatter)
        LOGGER.addHandler(handler)
        LOGGER.propagate = False
