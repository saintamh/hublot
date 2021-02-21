#!/usr/bin/env python3

# standards
from http.cookiejar import CookiePolicy

# 3rd parties
from requests import Response


class ForbanCookiePolicy(CookiePolicy):

    netscape = True
    rfc2965 = False
    hide_cookie2 = False

    def __init__(self, cookies_enabled: bool):
        super().__init__()
        self.cookies_enabled = cookies_enabled

    def set_ok(self, cookie, request):
        return self.cookies_enabled

    def return_ok(self, cookie, request):
        return self.cookies_enabled

    def domain_return_ok(self, domain, request):
        return self.cookies_enabled

    def path_return_ok(self, path, request):
        return self.cookies_enabled


class MockResponse:

    def __init__(self, response: Response):
        self.response = response

    def info(self):
        return self

    def get_all(self, name, failobj=None):
        # This is a mock of `email.message.EmailMessage.get_all` -- ``Return a list of all the values for the field named name. If
        # there are no such named headers in the message, failobj is returned''
        #
        # See https://docs.python.org/3.8/library/email.message.html#email.message.EmailMessage.get_all
        if callable(getattr(self.response.headers, 'get_all', None)):
            # It must be that `headers` is a `MultipleCaseInsensitiveDict` that we created when loading from cache. It gives us the
            # un-joined cookies, use that
            return self.response.headers.get_all(name, failobj)
        else:
            # Fall back to reading from the ', '-joined string.
            if name in self.response.headers:
                return [self.response.headers[name]]
        return failobj
