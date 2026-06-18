"""Supabase client (§15). Lazy singleton so importing the module never does I/O
(keeps the scorer import graph pure for tests)."""
from __future__ import annotations

from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_client():
    """Return a cached Supabase client. Raises if env not configured."""
    from supabase import create_client  # imported lazily — not needed for scorer tests

    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set (see backend/.env.example)")
    return create_client(settings.supabase_url, settings.supabase_key)
