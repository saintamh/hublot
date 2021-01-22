#!/usr/bin/env python3

# We use `Response` object internals in here, we're ok with that, pylint: disable=protected-access

# standards
from contextlib import contextmanager
from dataclasses import dataclass
import gzip
from hashlib import md5
from pathlib import Path
import pickle
import re
import sqlite3
from typing import Optional, Tuple, Union

# 3rd parties
from requests import PreparedRequest, Response

# forban
from .logs import LogEntry


UserSpecifiedCacheKey = Union['CacheKey', Tuple[str, ...], str]


@dataclass
class CacheKey:

    parts: Tuple[str, ...]

    @property
    def path_parts(self) -> Tuple[str, ...]:
        return tuple(
            re.sub(r'[^\w\-\.]', lambda m: f'%{ord(m.group()):02X}', part)
            for part in self.parts
        )

    @property
    def unique_str(self) -> str:
        # NB the string we return isn't for use in paths, so we can use '/' as the separator regardless of platform. Slashes have
        # been removed from the parts, so this is unambiguous.
        return '/'.join(self.path_parts)

    @classmethod
    def parse(cls, key: UserSpecifiedCacheKey) -> 'CacheKey':
        if isinstance(key, CacheKey):
            return key
        elif isinstance(key, tuple):
            return cls(key)
        elif isinstance(key, str):
            return cls((key,))
        else:
            raise TypeError(repr(key))


class HeaderStorage:
    """
    Stores the header information from cached Responses.
    """

    def __init__(self, root_path: Path):
        root_path.mkdir(parents=True, exist_ok=True)
        db_file_path = root_path / 'forban.sqlite3'
        self.db = sqlite3.connect(db_file_path)
        self._init_db()

    @contextmanager
    def _cursor(self):
        cursor = self.db.cursor()
        yield cursor
        self.db.commit()

    def _init_db(self):
        with self._cursor() as cursor:
            cursor.execute(
                '''
                    CREATE TABLE IF NOT EXISTS "forban_headers" (
                       "key" TEXT NOT NULL PRIMARY KEY,
                       "pickled_response" BLOB NOT NULL
                    );
                '''
            )

    def select(self, key: CacheKey) -> Optional[Response]:
        with self._cursor() as cursor:
            cursor.execute(
                '''
                    SELECT "pickled_response"
                    FROM "forban_headers"
                    WHERE "key"=?;
                ''',
                [key.unique_str],
            )
            row = next(cursor, None)
            if row:
                response = pickle.loads(row[0])
                return response
        return None

    def insert(self, key: CacheKey, res: Response) -> None:
        # body content is stored separately in BodyStorage, and we don't want to modify as a side-effect the `Response` object
        # we've been given, so we just check the body's already been nulled.
        assert res._content_consumed  # type: ignore
        assert res._content is None  # type: ignore
        pickled_response = pickle.dumps(res)
        with self._cursor() as cursor:
            cursor.execute(
                '''
                    INSERT OR REPLACE INTO "forban_headers"
                    VALUES (?, ?);
                ''',
                [key.unique_str, pickled_response],
            )

    def delete(self, key: CacheKey) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                '''
                    DELETE FROM "forban_headers"
                    WHERE "key"=?;
                ''',
                [key.unique_str],
            )

    def count(self) -> int:
        with self._cursor() as cursor:
            cursor.execute(
                '''
                    SELECT COUNT(1) FROM "forban_headers";
                ''',
            )
            return next(cursor)[0]


class BodyStorage:
    """
    Stores the body data from cached responses. It's important to keep these in flat files so that they can easily be inspected for
    debugging -- if they were just pickled `Response` objects it wouldn't be very convenient. It's part of the contract for this
    class that the storage files are always just the gzipped body.
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path

    def read(self, key: CacheKey) -> Optional[bytes]:
        file_path = self.file_path(key)
        if file_path.exists():
            with gzip.open(file_path, 'rb') as file_in:
                return file_in.read()
        return None

    def write(self, key: CacheKey, body: bytes) -> None:
        file_path = self.file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, 'wb') as file_out:
            file_out.write(body)

    def file_path(self, key: CacheKey) -> Path:
        file_path = self.root_path / Path(*key.path_parts)
        if not file_path.suffix == '.gz':
            file_path = file_path.parent / f'{file_path.name}.gz'
        return file_path


class DiskCache:

    def __init__(self, root_path: Union[str, Path]):
        if not isinstance(root_path, Path):
            root_path = Path(root_path)
        self.root_path = root_path
        self.headers = HeaderStorage(root_path)
        self.bodies = BodyStorage(root_path)

    def get(
        self,
        prepared_req: PreparedRequest,
        log: LogEntry,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> Optional[Response]:
        """
        Looks up the given `PreparedRequest`, and returns the corresponding `Response` if it was in cache, or `None` otherwise.
        """
        key = self.compute_key(prepared_req) if key is None else CacheKey.parse(key)
        res = self.headers.select(key)
        if res is not None:
            body = self.bodies.read(key)
            if body is None:
                # file must've been manually deleted
                self.headers.delete(key)
                res = None
            else:
                res._content = body  # type: ignore
        log.cache_key_str = key.unique_str
        log.cached = (res is not None)
        return res

    def put(
        self,
        prepared_req: PreparedRequest,
        res: Response,
        key: Optional[UserSpecifiedCacheKey] = None,
    ) -> None:
        res, body = self._copy_response(res)  # before modifying it
        key = self.compute_key(prepared_req) if key is None else CacheKey.parse(key)
        self.headers.insert(key, res)
        self.bodies.write(key, body)

    @staticmethod
    def _copy_response(res: Response) -> Tuple[Response, bytes]:
        state = res.__getstate__()  # type: ignore
        body = state['_content']
        state['_content'] = None
        copy = Response()
        copy.__setstate__(state)  # type: ignore
        return copy, body

    @staticmethod
    def compute_key(prepared_req: PreparedRequest) -> CacheKey:
        # NB we don't normalise the order of the `params` dict or `data` dict. If running in Python 3.6+, where dicts preserve
        # their insertion order, multiple calls from the same code, where the params are defined in the same order, will hit the
        # same cache key. In previous versions, maybe not, so in 3.5 and before params and body should be serialised before being
        # sent to Forban.
        headers = sorted(
            (key.title(), value)
            for key, value in prepared_req.headers.items()
        )
        key = (
            prepared_req.method,
            prepared_req.url,
            headers,
            prepared_req.body,
        )
        hashed = md5(repr(key).encode('UTF-8')).hexdigest()
        return CacheKey((hashed[:3], hashed[3:]))
