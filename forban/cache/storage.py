#!/usr/bin/env python3

# standards
import gzip
from pathlib import Path
from typing import Optional

# 3rd parties
from requests import Response

# forban
from .binaryblob import compose_binary_blob, parse_binary_blob
from .key import CacheKey


class Storage:

    def read(self, key: CacheKey) -> Optional[Response]:
        raise NotImplementedError

    def write(self, key: CacheKey, response: Response) -> None:
        raise NotImplementedError


class DiskStorage(Storage):

    def __init__(self, root_path: Path):
        self.root_path = root_path

    def read(self, key: CacheKey) -> Optional[Response]:
        file_path = self._file_path(key)
        if file_path.exists():
            with gzip.open(file_path, 'rb') as file_in:
                return parse_binary_blob(file_in.read())
        return None

    def write(self, key: CacheKey, response: Response) -> None:
        file_path = self._file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, 'wb') as file_out:
            file_out.write(compose_binary_blob(response))

    def _file_path(self, key: CacheKey) -> Path:
        file_path = self.root_path / Path(*key.path_parts)
        if not file_path.suffix == '.gz':
            file_path = file_path.parent / f'{file_path.name}.gz'
        return file_path
