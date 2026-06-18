"""Runtime config. Scoring weights are surfaced here on purpose (§16: weights
must be visible and tunable for defensibility)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_key: str = ""

    # Model family is an OPEN DECISION (§25) — kept configurable, not locked in code.
    llm_provider: str = "anthropic"
    llm_model_step: str = "claude-haiku-4-5-20251001"
    llm_model_synth: str = "claude-opus-4-8"
    llm_api_key: str = ""

    run_seed: int = 1337
    wcag_version: str = "2.2"
    slack_webhook_url: str = ""


settings = Settings()
