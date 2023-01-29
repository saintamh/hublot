#!/usr/bin/env python3

# standards
from abc import ABC

# 3rd parties
from requests import RequestException


class ScraperError(ABC, Exception):
    pass


# These are the exceptions that @retry_on_scraper_error handles by default. We register them as subclasses of `ScraperError`, as a
# convenience to user code, so that user code doesn't need to import requests just for that exception class.
#
# Sadly just `register`ing classes as "virtual" subclasses of `ScraperError` will not work for catching exceptions like this:
#
#   try:
#     something_risky()
#   except ScraperError:  # won't catch scraper errors!
#     ...
#
# This is known and won't be handled: https://github.com/python/cpython/pull/6461
#
# So this list is part of the exposed interface, and it can be used like this:
#
#   try:
#     something_risky()
#   except hublot.SCRAPER_ERRORS:  # this works
#     ...
#
SCRAPER_ERROR_TYPES = (
    ScraperError,
    ValueError,
    RequestException,
)


for cls in SCRAPER_ERROR_TYPES:
    if cls is not ScraperError:
        ScraperError.register(cls)
