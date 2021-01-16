#!/usr/bin/env python3

# We use `Response` object internals in here, we're ok with that, pylint: disable=protected-access

# standards
from contextlib import closing
import gzip
from hashlib import md5
from pathlib import Path
import pickle
import sqlite3
from typing import Optional, Tuple, Union

# 3rd parties
from requests import PreparedRequest, Response

# forban
from .logs import LogEntry


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
        with closing(self.db.cursor()) as cursor:
            cursor.execute(
                '''
                    CREATE TABLE IF NOT EXISTS "forban_headers" (
                       "key" TEXT NOT NULL PRIMARY KEY,
                       "pickled_response" BLOB NOT NULL
                    );
                '''
            )

    def select(self, cache_key: str) -> Optional[Response]:
        with closing(self.db.cursor()) as cursor:
            cursor.execute(
                '''
                    SELECT "pickled_response"
                    FROM "forban_headers"
                    WHERE "key"=?;
                ''',
                [cache_key],
            )
            row = next(cursor, None)
            if row:
                response = pickle.loads(row[0])
                return response
        return None

    def insert(self, cache_key: str, res: Response) -> None:
        # body content is stored separately in BodyStorage, and we don't want to modify as a side-effect the `Response` object
        # we've been given, so we just check the body's already been nulled.
        assert res._content_consumed  # type: ignore
        assert res._content is None  # type: ignore
        pickled_response = pickle.dumps(res)
        with closing(self.db.cursor()) as cursor:
            cursor.execute(
                '''
                    INSERT INTO "forban_headers"
                    VALUES (?, ?);
                ''',
                [cache_key, pickled_response],
            )

    def delete(self, cache_key: str) -> None:
        with closing(self.db.cursor()) as cursor:
            cursor.execute(
                '''
                    DELETE FROM "forban_headers"
                    WHERE "key"=?;
                ''',
                [cache_key],
            )

    def count(self) -> int:
        with closing(self.db.cursor()) as cursor:
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
                res._content = body  # type: ignore
        log.cache_key = key
        log.cached = (res is not None)
        return res

    def put(self, prepared_req: PreparedRequest, res: Response) -> None:
        res, body = self._copy_response(res)  # before modifying it
        key = self.compute_key(prepared_req)
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
