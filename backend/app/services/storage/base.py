"""Core abstraction, contracts, and error definitions for durable image storage."""

from __future__ import annotations

import abc
import hashlib
import re
from typing import Any


class StorageError(Exception):
    """Base exception for all image object storage failures."""
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ObjectNotFoundError(StorageError):
    """Raised when an object cannot be located in the storage bucket."""
    pass


class ImageIntegrityMismatchError(StorageError):
    """Raised when downloaded image bytes do not match expected cryptographic hash."""
    pass


_SAFE_PATH_COMPONENT = re.compile(r"^[a-zA-Z0-9_-]+$")
_SAFE_EXTENSION = re.compile(r"^[a-zA-Z0-9]+$")


def build_deterministic_storage_path(
    inspection_id: str,
    sequence: int,
    normalized_hash: str,
    extension: str = "png",
) -> str:
    """Construct a safe, deterministic storage path for an inspection image.

    Format: inspections/{inspection_id}/images/{sequence}_{normalized_hash}.{extension}
    Example: inspections/7c9e6679-7425-40de-944b-e07fc1f90ae7/images/1_ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb.png
    """
    clean_id = str(inspection_id).strip()
    if not clean_id or ".." in clean_id or "/" in clean_id or "\\" in clean_id:
        raise ValueError(f"Invalid inspection_id for storage path: '{inspection_id}'")

    if sequence <= 0:
        raise ValueError(f"Sequence must be a positive integer, got {sequence}")

    clean_hash = str(normalized_hash).strip().lower()
    if not re.match(r"^[a-f0-9]{32,64}$", clean_hash):
        raise ValueError(f"Invalid normalized_hash format: '{normalized_hash}'")

    clean_ext = str(extension).strip().lstrip(".").lower()
    if not _SAFE_EXTENSION.match(clean_ext):
        clean_ext = "png"

    return f"inspections/{clean_id}/images/{sequence}_{clean_hash}.{clean_ext}"


def verify_image_bytes_integrity(
    data: bytes,
    expected_hash: str,
    path_context: str | None = None,
) -> bool:
    """Verify SHA-256 hash of image data matches expected normalized hash.

    Raises ImageIntegrityMismatchError if mismatch occurs. Returns True on success.
    """
    computed_hash = hashlib.sha256(data).hexdigest().lower()
    clean_expected = expected_hash.strip().lower()
    if computed_hash != clean_expected:
        ctx_info = f" for '{path_context}'" if path_context else ""
        raise ImageIntegrityMismatchError(
            f"Image integrity mismatch{ctx_info}: expected hash '{clean_expected}', got '{computed_hash}'.",
            details={
                "expected_hash": clean_expected,
                "computed_hash": computed_hash,
                "byte_count": len(data),
                "path_context": path_context,
            },
        )
    return True


class ImageStorage(abc.ABC):
    """Abstract object storage contract for persisting and retrieving image binaries."""

    @abc.abstractmethod
    def upload(
        self,
        path: str,
        data: bytes,
        content_type: str = "image/png",
        upsert: bool = True,
    ) -> str:
        """Upload raw image bytes to a deterministic path in the private bucket.

        Returns the stored object path.
        """
        pass

    @abc.abstractmethod
    def download(self, path: str) -> bytes:
        """Download raw image bytes from the private storage bucket.

        Raises ObjectNotFoundError if missing.
        """
        pass

    @abc.abstractmethod
    def delete(self, path: str) -> bool:
        """Delete an object from the private storage bucket.

        Returns True if deleted or already absent.
        """
        pass

    @abc.abstractmethod
    def exists(self, path: str) -> bool:
        """Check if an object exists in the private storage bucket."""
        pass
