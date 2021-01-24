#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
import logging
from time import sleep
import threading
from types import GeneratorType
from typing import Callable, Optional, Sequence

# forban
from .exceptions import ScraperError


@dataclass
class ThreadLocalData:
    force_cache_stale: bool = False
    logger: Optional[logging.Logger] = None


SCRAPER_LOCAL = threading.local()
SCRAPER_LOCAL.stack = [ThreadLocalData()]


def scraper(
    no_parens_function: Optional[Callable] = None,
    *,
    retry_on: Sequence[type] = (),
    num_attempts: int = 5,
):
    if no_parens_function:
        # decorator is without parentheses
        return scraper()(no_parens_function)

    @contextmanager
    def scraper_stack_frame():
        frame = ThreadLocalData()
        SCRAPER_LOCAL.stack.append(frame)
        try:
            yield frame
        finally:
            SCRAPER_LOCAL.stack.pop()

    retry_on = (ScraperError, *retry_on)

    def make_wrapper(function: Callable):
        @wraps(function)
        def wrapper(*args, **kwargs):
            with scraper_stack_frame() as frame:
                for attempt in range(num_attempts):
                    try:
                        if attempt > 0:
                            frame.force_cache_stale = True
                        payload = function(*args, **kwargs)
                        if isinstance(payload, GeneratorType):
                            payload = list(payload)
                        return payload
                    except Exception as error:  # pylint: disable=broad-except
                        if isinstance(error, retry_on) and attempt < num_attempts - 1:
                            delay = 5 ** attempt
                            if frame.logger:
                                frame.logger.error('%s: %s - sleeping %ds', type(error).__name__, error, delay)
                            sleep(delay)
                        else:
                            raise
        return wrapper
    return make_wrapper
