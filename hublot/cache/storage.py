#!/usr/bin/env python3

# standards
from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime, timedelta
import gzip
import logging
from pathlib import Path
import re
from typing import Optional

# hublot
from ..datastructures import Response
from .binaryblob import compose_binary_blob, parse_binary_blob
from .key import CacheKey


class Storage(ABC):  # pragma: no-cover
    @abstractmethod
    def read(self, key: CacheKey, max_age: Optional[timedelta] = None) -> Optional[Response]: ...

    @abstractmethod
    def write(self, key: CacheKey, response: Response) -> None: ...

    @abstractmethod
    def iter_all_keys(self) -> Iterable[CacheKey]: ...

    @abstractmethod
    def prune(self, max_age: timedelta) -> None: ...


class DiskStorage(Storage):
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path

    def read(self, key: CacheKey, max_age: Optional[timedelta] = None) -> Optional[Response]:
        file_path = self._file_path(key)
        if not file_path.exists():
            return None
        if max_age is not None:
            file_age = current_datetime() - datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_age > max_age:
                return None
        try:
            with gzip.open(file_path, "rb") as file_in:
                binary_blob = file_in.read()
        except Exception as error:  # pragma: no cover
            logging.error("Couldn't read %s: %s", file_path, error)
            return None
        return parse_binary_blob(binary_blob)

    def write(self, key: CacheKey, response: Response) -> None:
        file_path = self._file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(file_path, "wb") as file_out:
            file_out.write(compose_binary_blob(response))

    def iter_all_keys(self) -> Iterable[CacheKey]:
        for file_path in self._iter_all_files():
            parts = list(file_path.relative_to(self.root_path).parts)
            parts[-1] = re.sub(r"\.gz$", "", file_path.name)
            yield CacheKey.from_path_parts(parts)

    def prune(self, max_age: timedelta) -> None:
        now = current_datetime()
        dirs_to_check = set()
        for file_path in self._iter_all_files():
            file_age = now - datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_age > max_age:
                file_path.unlink()
                dirs_to_check.add(file_path.parent)
        for file_parent in dirs_to_check:
            dir_path = file_parent
            while dir_path != self.root_path and not next(dir_path.iterdir(), None):
                dir_path.rmdir()
                dir_path = dir_path.parent

    def _iter_all_files(self) -> Iterable[Path]:
        return self.root_path.glob("**/*.gz")

    def _file_path(self, key: CacheKey) -> Path:
        file_path = self.root_path / Path(*key.path_parts)
        if not file_path.suffix == ".gz":
            file_path = file_path.parent / f"{file_path.name}.gz"
        return file_path


def current_datetime() -> datetime:
    # This is put in a separate function so that tests can patch that function
    return datetime.now()
