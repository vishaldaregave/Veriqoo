"""Thread-safe in-memory image storage for unit testing and offline execution."""

from __future__ import annotations

import threading
from typing import Any

from backend.app.services.storage.base import (
    ImageStorage,
    ObjectNotFoundError,
    StorageError,
)


class InMemoryImageStorage(ImageStorage):
    """Deterministic in-memory fake object storage."""

    def __init__(self, bucket_name: str = "inspection-images") -> None:
        self.bucket_name = bucket_name
        self._lock = threading.RLock()
        self._storage: dict[str, bytes] = {}

    def _validate_path(self, path: str) -> str:
        clean = str(path).strip()
        if not clean or clean.startswith("/") or clean.startswith("\\") or ".." in clean:
            raise ValueError(f"Invalid or unsafe storage path: '{path}'")
        return clean

    def upload(
        self,
        path: str,
        data: bytes,
        content_type: str = "image/png",
        upsert: bool = True,
    ) -> str:
        clean_path = self._validate_path(path)
        with self._lock:
            if not upsert and clean_path in self._storage:
                raise StorageError(f"Object already exists at '{clean_path}' and upsert is False.")
            self._storage[clean_path] = bytes(data)
            return clean_path

    def download(self, path: str) -> bytes:
        clean_path = self._validate_path(path)
        with self._lock:
            if clean_path not in self._storage:
                raise ObjectNotFoundError(f"Object '{clean_path}' not found in bucket '{self.bucket_name}'.")
            return bytes(self._storage[clean_path])

    def delete(self, path: str) -> bool:
        clean_path = self._validate_path(path)
        with self._lock:
            if clean_path in self._storage:
                del self._storage[clean_path]
                return True
            return False

    def exists(self, path: str) -> bool:
        try:
            clean_path = self._validate_path(path)
        except ValueError:
            return False
        with self._lock:
            return clean_path in self._storage

    def list_objects(self, prefix: str = "") -> list[str]:
        clean_prefix = prefix.strip().lstrip("/")
        with self._lock:
            if not clean_prefix:
                return sorted(list(self._storage.keys()))
            return sorted([k for k in self._storage.keys() if k.startswith(clean_prefix)])

    def clear(self) -> None:
        with self._lock:
            self._storage.clear()
