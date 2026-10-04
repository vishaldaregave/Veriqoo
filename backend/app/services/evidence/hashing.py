"""Deterministic cryptographic hashing for Phase 5A image evidence."""

from __future__ import annotations

import hashlib


def compute_sha256(data: bytes) -> str:
    """Compute deterministic lowercase SHA-256 hex digest for given raw bytes."""
    return hashlib.sha256(data).hexdigest()


def derive_image_id(normalized_hash: str, prefix: str = "img_") -> str:
    """Derive deterministic, stable image identity from the normalized content hash.

    Uses the first 16 characters of the SHA-256 normalized hash with a domain prefix.
    """
    if not normalized_hash:
        raise ValueError("Cannot derive image ID from an empty hash.")
    return f"{prefix}{normalized_hash[:16]}"

