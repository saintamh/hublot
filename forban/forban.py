#!/usr/bin/env python3

# standards
from contextlib import contextmanager
from dataclasses import dataclass
import gzip
from hashlib import md5
import logging
from pathlib import Path
import pickle
import sqlite3
from time import sleep, time
from typing import Any, Callable, Optional, Union
from urllib.parse import urlparse

# 3rd parties
from requests import PreparedRequest, Request, RequestException, Response, Session


@dataclass(frozen=False)
class LogEntry:
    prepared_req: PreparedRequest
    cache_key: str = None
    cached: bool = None
    courtesy_seconds: int = None

    def _compose_line(self):
        if self.cache_key:
            yield f'[{self.cache_key}] '
        if self.cached:
            yield '[cached] '
        elif (self.courtesy_seconds or 0) > 0.5:
            seconds = f'{round(self.courtesy_seconds)}s'
            yield f'[{seconds:^6s}] '
        else:
            yield '         '
        pr = self.prepared_req
        yield pr.url
        if pr.method != 'GET':
            yield f'[{pr.method}'
            try:
                length = int(pr.headers.get('Content-Length', 0))
            except ValueError:
                length = 0
            if length > 0:
                yield f' {length} bytes'
            yield ']'

    def __str__(self):
        return ''.join(self._compose_line())


class HeaderStorage:
    """
    Stores the header information from cached Responses. 
    """

    def __init__(self, root_path: Path):
        root_path.mkdir(parents=True, exist_ok=True)
        db_file_path = root_path / 'forban.sqlite3'
        self.db = sqlite3.connect(db_file_path)
        self._init_db()

    def _init_db(self):
        with self.db.cursor() as cursor:
            cursor.execute(
                '''
                    CREATE TABLE IF NOT EXISTS "forban_headers" (
                       "key" TEXT NOT NULL PRIMARY KEY,
                       "pickled_response" BLOB NOT NULL,
                    );
                '''
            )

    def select(self, cache_key: str) -> Optional[Response]:
        with self.db.cursor() as cursor:
            cursor.execute(
                '''
                    SELECT "pickled_response"
                    FROM "forban_headers"
                    WHERE "key"=?;
                ''',
                cache_key,
            )
            row = next(cursor, None)
            if row:
                response = pickle.loads(row[0])
                return response
        return None

    def insert(self, cache_key: str, res: Response) -> None:
        assert res._content_consumed
        res._content = None  # body content is stored separately in BodyStorage
        pickled_response = pickle.dumps(res)
        with self.db.cursor() as cursor:
            cursor.execute(
                '''
                    INSERT INTO "forban_headers"
                    VALUES (?, ?);
                ''',
                [(cache_key, pickled_response)],
            )

    def delete(self, cache_key: str) -> None:
        with self.db.cursor() as cursor:
            cursor.execute(
                '''
                    DELETE FROM "forban_headers"
                    WHERE "key"=?;
                ''',
                cache_key,
            )


class BodyStorage:
    """
    Stores the body data from cached responses. It's important to keep these in flat files 
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path

    def read(self, cache_key: str) -> Optional[bytes]:
        file_path = self.file_path(cache_key)
        if file_path.exists():
            with gzip.open(file_path, 'rb') as file_in:
                return file_in.read()
        return None

    def write(self, cache_key: str, body: bytes) -> None:
        file_path = self.file_path(cache_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, 'wb') as file_out:
            file_out.write(body)

    def file_path(self, cache_key: str) -> Path:
        return self.root_path / cache_key[:3] / f'{cache_key[3:]}.gz'


class Cache:

    def __init__(self, root_path: Union[str, Path]):
        if not isinstance(root_path, Path):
            root_path = Path(root_path)
        self.root_path = root_path
        self.headers = HeaderStorage(root_path)
        self.bodies = BodyStorage(root_path)

    def get(self, prepared_req: PreparedRequest, log: LogEntry) -> Optional[Response]:
        """
        Looks up the given `PreparedRequest`, and returns the corresponding `Response` if it was in cache, or `None` otherwise.
        """
        key = self.compute_key(prepared_req)
        res = self.headers.select(key)
        if res is not None:
            body = self.bodies.read(key)
            if body is None:
                # file must've been manually deleted
                self.headers.delete(key)
                res = None
            else:
                body._content = body
        log.cache_key = key
        log.cached = (res is not None)
        return res

    def put(self, prepared_req: PreparedRequest, res: Response) -> None:
        key = self.compute_key(prepared_req)
        self.headers.insert(key, res)
        self.bodies.write(key, res)

    @staticmethod
    def compute_key(prepared_req: PreparedRequest):
        # NB we don't normalise the order of the `params` dict or `data` dict. If running in Python 3.6+, where dicts preserve
        # their insertion order, multiple calls from the same code, where the params are defined in the same order, will hit the
        # same cache key. In previous versions, maybe not, so in 3.5 and before params and body should be serialised before being
        # sent to Forban.
        headers = {
            key.title(): value
            for key, value in prepared_req.headers.items()
        }
        key = (
            prepared_req.method,
            prepared_req.url,
            headers,
            prepared_req.body,
        )
        return md5(repr(key).encode('UTF-8')).hexdigest()


class CourtesySleep:

    def __init__(self, courtesy_seconds: int):
        self.courtesy_seconds = courtesy_seconds
        self.last_request_per_host = {}

    @contextmanager
    def __call__(self, req: Request, log: LogEntry, courtesy_seconds: Optional[int] = None):
        if courtesy_seconds is None:
            courtesy_seconds = self.courtesy_seconds
        host = urlparse(req.url).hostname
        last_request = self.last_request_per_host.get(host, 0)
        delay = (last_request + courtesy_seconds) - time()
        if delay > 0:
            log.courtesy_seconds = delay
            sleep(delay)
        try:
            yield
        finally:
            # NB we store the time after the request is complete
            self.last_request_per_host[host] = time()


class Client:

    def __init__(
        self,
        cache: Cache = None,
        session: Session = None,
        courtesy_sleep: Union[CourtesySleep, int] = 5,
        propagate_logs: bool = False,
    ):
        self.logger = self._init_logger(propagate_logs)
        self.cache = cache
        self.session = session or Session()
        if not isinstance(courtesy_sleep, CourtesySleep):
            courtesy_sleep = CourtesySleep(courtesy_sleep)  # malkovitch malkovitch
        self.courtesy_sleep = courtesy_sleep

    def fetch_and_parse(
        self,
        url: str,
        parse: Callable[[Response], Any],
        num_attempts: int=5,
        **kwargs,
    ) -> Any:
        for attempt in range(num_attempts):
            try:
                if attempt > 0:
                    kwargs['force_cache_stale'] = True
                return parse(self.fetch(url, **kwargs))
            except (ValueError, RequestException) as error:
                if attempt < num_attempts - 1:
                    delay = 5 ** attempt
                    self.logger.error('%s: %s - sleeping %ds', type(error).__name__, error, delay)
                    sleep(delay)
                else:
                    raise

    def fetch(
        self,
        url: str,
        force_cache_stale: bool = False,
        courtesy_seconds: Optional[int] = None,
        **kwargs,
    ) -> Response:
        method = kwargs.pop('method', 'GET').upper()
        req = Request(
            url=url,
            method=method,
            headers=kwargs.get('headers'),
            files=kwargs.get('files'),
            data=kwargs.get('data') or {},
            json=kwargs.get('json'),
            params=kwargs.get('params') or {},
            auth=kwargs.get('auth'),
            cookies=kwargs.get('cookies'),
        )
        prepared_req = self.session.prepare_request(req)
        log = LogEntry(req)
        res = None
        if self.cache and not force_cache_stale:
            res = self.cache.get(prepared_req, log)
        if res is None:
            with self.courtesy_sleep(req, log, courtesy_seconds):
                res = self.session.request(method, url, **kwargs)
            if self.cache:
                self.cache.put(prepared_req, res)
        self.logger.info('%s', log)
        return res

    def get(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='GET', **kwargs)

    def options(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='OPTIONS', **kwargs)

    def head(self, url: str, **kwargs) -> Response:
        kwargs.setdefault('allow_redirects', False)
        return self.fetch(url, method='HEAD', **kwargs)

    def post(self, url: str, data=None, json=None, **kwargs) -> Response:
        return self.fetch(url, method='POST', data=data, json=json, **kwargs)

    def put(self, url: str, data=None, **kwargs) -> Response:
        return self.fetch(url, method='PUT', data=data, **kwargs)

    def patch(self, url: str, data=None, **kwargs) -> Response:
        return self.fetch(url, method='PATCH', data=data, **kwargs)

    def delete(self, url: str, **kwargs) -> Response:
        return self.fetch(url, method='DELETE', **kwargs)

    @staticmethod
    def _init_logger(propagate: bool):
        logger = logging.getLogger('forban')
        if not propagate:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s', None, '%')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.propagate = False
        return logger
