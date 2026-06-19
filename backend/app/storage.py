"""Supabase Storage uploads (§14/§17).

Best-effort artifact upload. Per-step screenshots and the rendered evidence pack
(PDF + JSON) are pushed to a Storage bucket; the returned public URLs are persisted
in `screen_events.screenshot_url` and `evidence_packs.pdf_url`/`json_url`.

Every helper is DEFENSIVE: any failure (no bucket, no network, an old client, a
fake client in tests with no `.storage`) returns `None` so the caller falls back to
the local path and persistence never breaks (§15). Imports of the renderer are
deferred so importing this module stays I/O- and reportlab-free.
"""
from __future__ import annotations

import logging
import mimetypes

from app.config import settings

logger = logging.getLogger(__name__)


def _bucket(client):
    """Return the configured Storage bucket handle, or None if unavailable."""
    storage = getattr(client, "storage", None)
    if storage is None:
        return None
    return storage.from_(settings.storage_bucket)


def upload_bytes(client, data: bytes, dest_path: str, content_type: str) -> str | None:
    """Upload raw bytes to `dest_path` in the bucket; return the public URL or None."""
    bucket = _bucket(client)
    if bucket is None:
        return None
    try:
        bucket.upload(
            dest_path,
            data,
            {"content-type": content_type, "upsert": "true"},
        )
        return bucket.get_public_url(dest_path) or None
    except Exception as exc:  # noqa: BLE001 — best-effort; fall back to local ref
        logger.warning("storage upload failed for %s: %s", dest_path, exc)
        return None


def upload_file(client, local_path: str, dest_path: str) -> str | None:
    """Read a local file and upload it; return the public URL or None on any error."""
    try:
        with open(local_path, "rb") as f:
            data = f.read()
    except OSError as exc:
        logger.warning("storage read failed for %s: %s", local_path, exc)
        return None
    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    return upload_bytes(client, data, dest_path, content_type)


def upload_pack(client, pack: dict, run_id: str) -> tuple[str | None, str | None]:
    """Render the evidence pack (JSON + PDF) and upload both.

    Returns `(pdf_url, json_url)`. When storage is unavailable returns `(None, None)`
    WITHOUT rendering — so the no-storage path (and tests) pay no reportlab cost.
    """
    if _bucket(client) is None:
        return None, None

    from app.evidence.export import pack_to_json_bytes, pack_to_pdf_bytes

    json_url = upload_bytes(
        client, pack_to_json_bytes(pack), f"{run_id}/evidence.json", "application/json"
    )
    try:
        pdf_bytes = pack_to_pdf_bytes(pack)
    except Exception as exc:  # noqa: BLE001 — render failure must not break persistence
        logger.warning("pdf render failed for run %s: %s", run_id, exc)
        return None, json_url
    pdf_url = upload_bytes(client, pdf_bytes, f"{run_id}/evidence.pdf", "application/pdf")
    return pdf_url, json_url
