"""Storage upload tests (§14/§17) — fully offline with a fake Supabase client.

Covers: bytes/file upload returns the public URL; missing local file → None; a
client without `.storage` (the no-storage path) → None and NO render; upload_pack
returns (pdf_url, json_url) and renders only when storage is present.
"""
from __future__ import annotations

from app import storage


class _FakeBucket:
    def __init__(self, sink, fail=False):
        self.sink, self.fail = sink, fail

    def upload(self, path, data, opts):
        if self.fail:
            raise RuntimeError("boom")
        self.sink.append((path, data, opts))
        return None

    def get_public_url(self, path):
        return f"https://cdn.example/{storage.settings.storage_bucket}/{path}"


class _FakeStorage:
    def __init__(self, sink, fail=False):
        self._bucket = _FakeBucket(sink, fail)

    def from_(self, name):
        return self._bucket


class _FakeClient:
    def __init__(self, sink, fail=False):
        self.storage = _FakeStorage(sink, fail)


class _NoStorageClient:
    pass


def test_upload_bytes_returns_public_url():
    sink: list = []
    url = storage.upload_bytes(_FakeClient(sink), b"abc", "r1/a.json", "application/json")
    assert url and url.endswith("/r1/a.json")
    assert sink[0][2] == {"content-type": "application/json", "upsert": "true"}


def test_upload_bytes_swallows_errors():
    assert storage.upload_bytes(_FakeClient([], fail=True), b"x", "p", "text/plain") is None


def test_upload_bytes_no_storage_returns_none():
    assert storage.upload_bytes(_NoStorageClient(), b"x", "p", "text/plain") is None


def test_upload_file_reads_and_uploads(tmp_path):
    f = tmp_path / "shot.png"
    f.write_bytes(b"\x89PNG")
    sink: list = []
    url = storage.upload_file(_FakeClient(sink), str(f), "r1/step_0.png")
    assert url and url.endswith("/r1/step_0.png")
    assert sink[0][1] == b"\x89PNG"
    assert sink[0][2]["content-type"] == "image/png"


def test_upload_file_missing_returns_none():
    assert storage.upload_file(_FakeClient([]), "/nope/missing.png", "r1/x.png") is None


def test_upload_pack_no_storage_skips_render():
    # No `.storage` → (None, None) and the renderer is never imported/called.
    assert storage.upload_pack(_NoStorageClient(), {"app": "X"}, "r1") == (None, None)


def test_upload_pack_uploads_json_and_pdf():
    sink: list = []
    pack = {
        "app": "DemoBank",
        "generated_at": "2026-06-19T00:00:00Z",
        "inclusion_score": 80,
        "matrix": {"steps": [], "rows": []},
        "remediation": [],
        "personas": [],
        "wcag_summary": {},
    }
    pdf_url, json_url = storage.upload_pack(_FakeClient(sink), pack, "r1")
    assert json_url and json_url.endswith("/r1/evidence.json")
    assert pdf_url and pdf_url.endswith("/r1/evidence.pdf")
    paths = [p for p, _, _ in sink]
    assert "r1/evidence.json" in paths and "r1/evidence.pdf" in paths
