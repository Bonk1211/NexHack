"""Runtime config. Scoring weights are surfaced here on purpose (§16: weights
must be visible and tunable for defensibility)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_key: str = ""
    storage_bucket: str = "evidence"   # Supabase Storage bucket for screenshots + packs
    artifacts_dir: str = ".artifacts"  # local per-run screenshot store (served at /artifacts)

    # Model family LOCKED to DeepSeek V4 (§25 resolved). Two-tier: cheap per-step
    # vision (flash), larger once-per-run synthesis (pro). The client is DeepSeek-only
    # by construction (app.agents.llm), so there is no provider switch to misconfigure.
    llm_model_step: str = "deepseek-v4-flash"      # comprehend (per-step vision)
    llm_model_synth: str = "deepseek-v4-pro"       # synthesize (once per run)
    llm_api_key: str = ""                          # empty => deterministic offline fallback
    llm_base_url: str = "https://api.deepseek.com"  # OpenAI-compatible endpoint
    llm_pricing: str = (
        '{"deepseek-v4-flash":{"prompt":0.00014,"completion":0.00028},'
        '"deepseek-v4-pro":{"prompt":0.00174,"completion":0.00348}}'
    )
    # Source: DeepSeek V4 pricing (Apidog, Apr 24 2026) — USD per 1K tokens
    llm_pricing_currency: str = "USD"

    dashscope_api_key: str = ""          # Alibaba DashScope — figurine image generation
    figurine_bucket: str = "figurine"    # Supabase Storage bucket for figurine PNGs

    cors_origins: list[str] = ["*"]

    run_seed: int = 1337
    wcag_version: str = "2.2"
    slack_webhook_url: str = ""

    # Customer-facing plan quota (§SaaS revamp) — runs/month included in the plan.
    # Operational cost tracking (llm_pricing above) stays internal; this is the
    # number shown to the customer instead.
    plan_run_quota: int = 500

    # Per-persona crash-resume checkpoint store (§8 run graph).
    checkpoint_db: str = "checkpoints.sqlite"


settings = Settings()
