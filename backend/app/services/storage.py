"""Photo storage: local disk in development, Supabase Storage in production.

Images are stored under a key like "12/color_reference_ab12cd34ef.jpg"; `url(key)` turns
that into something a browser can load.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from app.config import settings


class StorageError(RuntimeError):
    pass


def _supabase_headers(content_type: str | None = None) -> dict:
    key = settings.supabase_secret_key or ""
    headers = {"apikey": key}
    # New "sb_secret_..." keys are not JWTs and go only in `apikey`; legacy service_role JWTs also need Bearer.
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def save(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    if settings.storage_backend == "supabase":
        if not (settings.supabase_url and settings.supabase_secret_key):
            raise StorageError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set for STORAGE_BACKEND=supabase")
        r = httpx.post(f"{settings.supabase_url}/storage/v1/object/{settings.supabase_bucket}/{key}",
                       content=data, headers={**_supabase_headers(content_type), "x-upsert": "true"}, timeout=30)
        if r.status_code >= 400:
            raise StorageError(f"Supabase upload failed ({r.status_code}): {r.text[:200]}")
        return key
    path = Path(settings.upload_dir) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def url(key: str) -> str:
    if settings.storage_backend == "supabase":
        return f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_bucket}/{key}"
    return f"/uploads/{key}"


def clear_local() -> None:
    import shutil
    if settings.storage_backend != "supabase":
        shutil.rmtree(settings.upload_dir, ignore_errors=True)
