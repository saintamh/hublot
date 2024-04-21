#!/usr/bin/env python3

# standards
from dataclasses import dataclass, replace
import json
from typing import (
    # We use the title-cased Dict, List and Tuple for backwards compat with pythons <3.9
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

# 3rd parties
import chardet
import requests
from requests.cookies import MockRequest, MockResponse, RequestsCookieJar
from requests.utils import get_encoding_from_headers


JsonValue = Union[
    None,
    str,
    int,
    float,
    bool,
    List["JsonValue"],
    Tuple["JsonValue"],
    Dict[str, "JsonValue"],
]


class Headers:
    """
    A headers dict that uses case-insensitive keys and allows multiple values per key (for e.g. repeated "Set-Cookie" headers).

    Note that we deliberately don't inherit from `abc.Mapping` or similar because the interface isn't _quite_ that of a dict,
    because some methods return strings, and some return lists of strings.
    """

    _dict: Dict[str, List[Tuple[str, str]]]

    def __init__(self, base: Optional[Union["Headers", Dict[str, str]]] = None) -> None:
        self._dict = {}
        if base:
            for key, value in base.items():
                self.add(key, value)

    def __bool__(self) -> bool:
        return bool(self._dict)

    def __contains__(self, key: str) -> bool:
        return key.title() in self._dict

    def __getitem__(self, key: str) -> str:
        """
        Return the headers with the given key, as a single string. This is for convenience -- in 99.99% of cases users expect a
        single value, and don't want to deal with a list that will only have one element in it. Use `get_all` if you want all
        values.
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        value_list = self.get_all(key)
        if not value_list:
            return default
        return "; ".join(value_list)

    def get_all(self, key: str, default: Sequence[str] = ()) -> Sequence[str]:
        value_list = self._dict.get(key.title())
        if value_list is None:
            return default
        return [value for _raw_key_unused, value in value_list]

    def add(self, key: str, value: str) -> None:
        self._dict.setdefault(key.title(), []).append((key, value))

    __setitem__ = add

    def setdefault(self, key: str, value: str) -> str:
        existing = self.get(key)
        if existing is not None:
            return existing
        else:
            self.add(key, value)
            return value

    def keys(self) -> Iterator[str]:
        """
        Yields a sequence of all header keys. Case-insensitive duplicates are removed.
        """
        for value_list in self._dict.values():
            yield value_list[0][0]

    __iter__ = keys

    def items(self, normalise_keys: bool = False) -> Iterator[Tuple[str, str]]:
        """
        Yield a sequence of all (key, value) header pairs. Note that unlike a proper dict, the sequence may include duplicated
        keys.

        Note that the `requests` library always normalises the casing of headers as they are sent out. For this reason our cache
        compares headers in a case-insensitive manner.
        """
        for normalised_key, value_list in self._dict.items():
            for raw_key, value in value_list:
                yield (normalised_key if normalise_keys else raw_key, value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Headers):
            return False
        return sorted(self.items(normalise_keys=True)) == sorted(other.items(normalise_keys=True))

    def __repr__(self) -> str:
        return "Headers({%s})" % ", ".join(f"{key!r}: {value!r}" for key, value in self.items())


@dataclass
class Request:
    """
    An HTTP request, as formulated by the user code. This class is deliberately modelled on the requests library's eponymous
    class, to make easy for clients to switch from that library to this. Like that class, this one provides flexibility and
    convenience by allowing multiple redundant ways of specifying the same request -- for instance you can use `json` or `data`.

    This does not currently support streaming requests. They could be implemented, as long as the CompiledRequest has a way of
    representing them that is universal across engines, and as long as the cache handles them correctly (presumably by mandating
    that streamed requests must have a manually specified cache key).
    """

    url: str
    method: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, str]] = None
    data: Optional[Union[bytes, str, Dict[str, object]]] = None
    json: Optional[JsonValue] = None
    auth: Optional[Tuple[str, str]] = None
    cookies: Optional[Dict[str, str]] = None

    def replace(self, **kwargs) -> "Request":
        return replace(self, **kwargs)

    @classmethod
    def build(cls, raw: object, **kwargs) -> "Request":
        if isinstance(raw, str):
            return Request(url=raw, **kwargs)
        if isinstance(raw, Request):
            return raw.replace(**kwargs)
        if isinstance(raw, requests.Request):
            if raw.auth is not None and not isinstance(raw.auth, tuple):
                raise NotImplementedError(type(raw.auth))  # need to convert to a tuple
            if raw.cookies is not None and not isinstance(raw.cookies, dict):
                raise NotImplementedError(type(raw.cookies))  # need to convert to a dict
            merged_kwargs = dict(
                url=raw.url,
                method=raw.method,
                headers=raw.headers,
                params=raw.params,
                data=raw.data,
                json=raw.json,
                auth=raw.auth,
                cookies=raw.cookies,
            )
            merged_kwargs.update(kwargs)
            return cls(**merged_kwargs)
        raise ValueError(f"Don't know how to make a Request from {raw!r}")


Requestable = Union[str, Request, requests.Request]


@dataclass
class CompiledRequest:
    """
    Similarly to the requests library's Request/PreparedRequest duo, this class serves as a companion to the above Request
    class. This class is considered private to Hublot; instances are built internally, and client code is not expected to handle
    them. It represents the HTTP request, ready to be sent to the server (or, more exactly in the case of this library, ready to be
    submitted to the client engine.

    This ends up re-implementing the core of the requests library's CompiledRequest class, but it was needed so that we know
    we're submitting the exact same request to all engines.
    """

    url: str
    method: str
    headers: Headers
    data: Optional[bytes]
    num_retries: int


@dataclass
class Response:
    """
    Public class for HTTP response. As with `Request`, the interface is deliberately copied from the corresponding class in the
    requests library, to ease transition.
    """

    request: CompiledRequest
    from_cache: bool
    history: List["Response"]

    status_code: int
    reason: Optional[str]
    headers: Headers
    content: bytes

    @property
    def url(self) -> str:
        return self.request.url

    @property
    def encoding(self) -> Optional[str]:
        """The declared character encoding of the response, if any."""
        return get_encoding_from_headers(self.headers)

    @property
    def text(self) -> str:
        encoding = self.encoding
        if encoding is None:
            encoding = chardet.detect(self.content)["encoding"]
        if encoding is None:
            raise CharsetDetectionFailure()
        return self.content.decode(encoding)

    # NB `json` could have `JsonValue` as its return type, but then it means all client code needs to perform type checks on the
    # returned value (e.g. assert it's a dict etc). Most clients know what the data is and just want to get on with it. So we make
    # it Any. Clients can still do manual type checks if they want.
    def json(self, **kwargs) -> Any:
        return json.loads(self.text, **kwargs)

    def raise_for_status(self) -> None:
        if 400 <= self.status_code < 600:
            raise HttpError(
                f"{self.status_code} Client Error: {self.reason} for url: {self.url}",
                response=self,
            )

    @property
    def ok(self) -> bool:
        try:
            self.raise_for_status()
        except HttpError:
            return False
        return True

    @property
    def is_redirect(self) -> bool:
        return "Location" in self.headers and self.status_code in {301, 302, 303, 307, 308}

    @property
    def cookies(self) -> RequestsCookieJar:
        cookies = RequestsCookieJar()
        get_cookies_from_response(cookies, self)
        return cookies


def get_cookies_from_response(cookies: RequestsCookieJar, res: Response) -> None:
    """
    Copy cookies from the given `Response` to our cookie jar.
    """
    # This code copied from `requests.cookies.extract_cookies_to_jar`. The code is meant for requests's own data structures,
    # but ours are compatible enough to fit.
    cookies.extract_cookies(MockResponse(res.headers), MockRequest(res.request))  # type: ignore


class HublotException(Exception):
    pass


ScraperError = HublotException  # for backwards compatibility with Hublot <2


class HttpError(HublotException):
    def __init__(self, message: str, response: Response) -> None:
        super().__init__(message)
        self.response = response


class TooManyRedirects(HublotException):
    pass


class CharsetDetectionFailure(HublotException):
    pass


class ConnectionError(HublotException):
    pass
