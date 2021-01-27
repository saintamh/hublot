#!/usr/bin/env python3

# standards
from http.cookiejar import CookiePolicy


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
