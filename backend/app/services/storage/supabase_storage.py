"""Supabase Storage HTTP REST client implementation for durable image storage."""

from __future__ import annotations

import logging
from typing import Any
import requests

from backend.app.config import Settings, get_settings
from backend.app.services.storage.base import (
    ImageStorage,
    ObjectNotFoundError,
    StorageError,
)

logger = logging.getLogger(__name__)


class SupabaseImageStorage(ImageStorage):
    """Production private Supabase Storage client."""

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        bucket_name: str | None = None,
        timeout: int = 30,
        settings: Settings | None = None,
        service_role_key: str | None = None,
        bucket: str | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self.url = (supabase_url or cfg.supabase_url).rstrip("/")
        # Backend uses service_role key if provided, otherwise anon key
        self.key = (
            service_role_key
            or supabase_key
            or getattr(cfg, "supabase_service_role_key", None)
            or cfg.supabase_anon_key
            or ""
        )
        self.bucket_name = (
            bucket
            or bucket_name
            or getattr(cfg, "supabase_storage_bucket", "inspection-images")
        )
        self.timeout = timeout

    def __repr__(self) -> str:
        masked_key = f"{self.key[:4]}...{self.key[-4:]}" if len(self.key) > 8 else "***"
        return f"<SupabaseImageStorage url='{self.url}' bucket='{self.bucket_name}' key='{masked_key}'>"

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }
        if extra:
            h.update(extra)
        return h

    def upload(
        self,
        path: str,
        data: bytes,
        content_type: str = "image/png",
        upsert: bool = True,
    ) -> str:
        """Upload image bytes to the private Supabase Storage bucket."""
        clean_path = path.lstrip("/")
        url = f"{self.url}/storage/v1/object/{self.bucket_name}/{clean_path}"

        headers = self._headers({
            "Content-Type": content_type or "image/png",
            "x-upsert": "true" if upsert else "false",
        })

        try:
            response = requests.post(
                url,
                headers=headers,
                data=data,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.error("Supabase Storage upload network failure for path '%s': %s", clean_path, exc)
            raise StorageError(
                f"Network failure uploading image to Supabase Storage: {str(exc)}",
                details={"path": clean_path, "bucket": self.bucket_name},
            ) from exc

        if response.status_code in (200, 201):
            return clean_path

        if response.status_code == 409 and upsert:
            # Handle conflict safely
            return clean_path

        error_msg = response.text[:200]
        logger.error(
            "Supabase Storage upload failed (%d) for path '%s': %s",
            response.status_code,
            clean_path,
            error_msg,
        )
        raise StorageError(
            f"Failed to upload image to Supabase Storage (HTTP {response.status_code}): {error_msg}",
            details={
                "status_code": response.status_code,
                "path": clean_path,
                "bucket": self.bucket_name,
            },
        )

    def download(self, path: str) -> bytes:
        """Download raw image bytes from the private bucket."""
        clean_path = path.lstrip("/")
        url = f"{self.url}/storage/v1/object/authenticated/{self.bucket_name}/{clean_path}"

        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
            )
            # Fallback to standard object endpoint if authenticated path returns 404 or 400
            if response.status_code != 200:
                fallback_url = f"{self.url}/storage/v1/object/{self.bucket_name}/{clean_path}"
                response = requests.get(
                    fallback_url,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
        except requests.RequestException as exc:
            logger.error("Supabase Storage download network failure for path '%s': %s", clean_path, exc)
            raise StorageError(
                f"Network failure downloading image from Supabase Storage: {str(exc)}",
                details={"path": clean_path, "bucket": self.bucket_name},
            ) from exc

        if response.status_code == 404:
            raise ObjectNotFoundError(
                f"Image object '{clean_path}' not found in bucket '{self.bucket_name}'.",
                details={"path": clean_path, "bucket": self.bucket_name},
            )

        if not response.ok:
            error_msg = response.text[:200]
            logger.error(
                "Supabase Storage download failed (%d) for path '%s': %s",
                response.status_code,
                clean_path,
                error_msg,
            )
            raise StorageError(
                f"Failed to download image from Supabase Storage (HTTP {response.status_code}): {error_msg}",
                details={
                    "status_code": response.status_code,
                    "path": clean_path,
                    "bucket": self.bucket_name,
                },
            )

        return response.content

    def delete(self, path: str) -> bool:
        """Delete an object from the private bucket."""
        clean_path = path.lstrip("/")
        url = f"{self.url}/storage/v1/object/{self.bucket_name}"

        try:
            response = requests.delete(
                url,
                headers=self._headers({"Content-Type": "application/json"}),
                json={"prefixes": [clean_path]},
                timeout=self.timeout,
            )
            return response.ok
        except requests.RequestException as exc:
            logger.error("Supabase Storage delete failure for path '%s': %s", clean_path, exc)
            return False

    def exists(self, path: str) -> bool:
        """Check if an object exists in the private bucket."""
        clean_path = path.lstrip("/")
        url = f"{self.url}/storage/v1/object/authenticated/{self.bucket_name}/{clean_path}"

        try:
            response = requests.head(
                url,
                headers=self._headers(),
                timeout=self.timeout,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
