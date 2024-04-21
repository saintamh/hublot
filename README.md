# Hublot

Hublot is a drop-in replacement for the
[requests](https://requests.readthedocs.io/) library that adds a number of
features:

- Multiple backends: the actual HTTP transactions can be performed by
  `requests` (the default), `PyCURL`, or the `curl` command-line. The interface
  is the same in all cases. This is helpful in getting around TLS
  fingerprinting.

- HTTP-level caching, with full replay capabilities. If you run the same script
  twice, on the second run no network requests will be made, and the script
  will receive the same responses.

- Per-host throttling. By default Hublot will enforce a 5 seconds courtesy
  delay between any two requests to the same host.

- Automatic retries with the `@retry_on_scraper_error` decorator. This handles
  network errors, HTTP status errors, and parser errors (i.e. if your scraper
  doesn't find the value it expected in the data). Failing requests will be
  re-submitted a few times, with exponential backoff between requests (i.e. it
  sleeps a little more after each consecutive failure).
