"""Shared test fixtures.

Force the whole suite OFFLINE for the LLM (§22: tests are network-free and
deterministic). pydantic-settings loads LLM_API_KEY from the .env FILE, so simply
unsetting the env var does NOT make a test offline — we must blank the loaded
setting. Tests that exercise the online path opt back in by monkeypatching a fake
client (see test_llm.py).
"""
from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _offline_llm(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
