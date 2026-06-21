"""Runtime config. Scoring weights are surfaced here on purpose (§16: weights
must be visible and tunable for defensibility)."""
from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_key: str = ""
    storage_bucket: str = "evidence"   # Supabase Storage bucket for screenshots + packs
    artifacts_dir: str = ".artifacts"  # local per-run screenshot store (served at /artifacts)

    # Qwen (Alibaba DashScope), OpenAI-compatible endpoint. Two-tier: cheap per-step
    # vision (flash), larger once-per-run synthesis (plus). The ChatDeepSeek client is a
    # ChatOpenAI subclass, so it drives any OpenAI-compatible endpoint unchanged (§25).
    llm_model_step: str = "qwen-flash"             # comprehend (per-step vision)
    llm_model_synth: str = "qwen3.7-plus"          # synthesize (once per run)
    # Reads DASHSCOPE_API_KEY (Qwen) or LLM_API_KEY; empty => deterministic offline fallback.
    llm_api_key: str = Field(
        default="", validation_alias=AliasChoices("LLM_API_KEY", "DASHSCOPE_API_KEY")
    )
    llm_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    # ponytail: pricing is indicative cost display only (not marks). Verify rates per
    # DashScope billing if cost accuracy matters; unknown keys just show $0.
    llm_pricing: str = (
        '{"qwen-flash":{"prompt":0.00005,"completion":0.0004},'
        '"qwen3.7-plus":{"prompt":0.0004,"completion":0.0012}}'
    )
    llm_pricing_currency: str = "USD"

    dashscope_api_key: str = ""          # Alibaba DashScope — figurine image generation
    figurine_bucket: str = "figurine"    # Supabase Storage bucket for figurine PNGs

    run_seed: int = 1337
    wcag_version: str = "2.2"
    slack_webhook_url: str = ""

    # Per-persona crash-resume checkpoint store (§8 run graph).
    checkpoint_db: str = "checkpoints.sqlite"


settings = Settings()
