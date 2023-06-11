#!/usr/bin/env python3

# standards
from abc import ABC, abstractmethod
from typing import ClassVar

# hublot
from ..config import Config
from ..datastructures import CompiledRequest, Response


class Engine(ABC):

    id: ClassVar[str]

    @abstractmethod
    def request(self, creq: CompiledRequest, config: Config) -> Response:
        """
        Perform one HTTP request, and return the response from the server, or raise an exception.

        Implementing subclasses should operate in a stateless fashion. In particular cookies will already be set as headers in the
        given `CompiledRequest`. The engine should not try to save or set cookies. This is important as it allows us to switch
        engines within a single session, carrying cookies across engines.

        Regardless of what `config.allow_redirects` it set to, the engine should not follow HTTP redirects. If a 30x response is
        received, the engine should just return that. Redirects are handled by the HttpClient class.

        The given CompiledRequest will already have Content-Length and Content-Type headers set, but we leave transport-related
        headers such as `Host`, `Connection` and `Accept-Encoding` headers up to the implementing subclass.
        """
