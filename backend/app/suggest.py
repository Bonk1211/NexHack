"""AI persona suggestion for a project.

Flow: POST /runs/apps/{app_id}/suggest-personas
  → reads app_demographics for the project
  → reads all personas from DB (id/slug, name, traits)
  → calls DeepSeek flash (same key/model as ethnicity inference in figurine.py)
  → parses JSON response into suggestion list
  → returns [] on any failure — never raises
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a UX accessibility expert helping choose user personas for accessibility audits. "
    "Given target demographics and an existing persona library, suggest which personas to use "
    "and what new ones to create to ensure thorough coverage. "
    "Return ONLY a valid JSON array — no markdown, no prose, no code fences."
)


def _build_prompt(app_name: str, demographics: list[dict], personas: list[dict]) -> str:
    demo_lines = "\n".join(
        f"- {d['label']}: {d.get('description') or '(no description)'}"
        for d in demographics
    ) or "(no demographics defined — infer from app name)"

    persona_lines = "\n".join(
        "  | ".join([
            p.get("slug", p.get("id", "?")),
            p.get("name", "?"),
            p.get("ageBand", p.get("age_band", "?")),
            p.get("language", "?"),
            ", ".join(p.get("disabilities", [])) or "none",
            str(round(float(p.get("techSavviness", p.get("tech_savviness", 0.5))), 1)),
        ])
        for p in personas
    ) or "(no existing personas)"

    return f"""App name: {app_name}

Target demographics:
{demo_lines}

Existing persona library (slug | name | age | language | disabilities | tech 0–1):
{persona_lines}

Suggest 3–5 personas that together cover the demographics above for an accessibility audit.
Prefer matching existing personas where they fit well. Propose new ones only where real gaps exist.

Return a JSON array where each item is one of:

For an existing persona match:
{{
  "type": "existing",
  "persona_id": "<slug from library>",
  "match_segment": "<demographic label this covers>",
  "match_reason": "<one sentence: why this persona fits the segment>",
  "match_detail": "<one sentence: the specific accessibility challenges this persona will surface in the audit>"
}}

For a new persona:
{{
  "type": "new",
  "name": "<realistic Malaysian name>",
  "label": "<role or disability descriptor>",
  "age_band": "<e.g. 55–64>",
  "language": "<e.g. Bahasa Melayu>",
  "disabilities": ["<e.g. low vision>"],
  "tech_savviness": <0.0–1.0>,
  "dwell_multiplier": <0.5–3.0>,
  "giveup_threshold_s": <10–120>,
  "misinterpret_prob": <0.0–1.0>,
  "match_segment": "<demographic label this covers>",
  "match_reason": "<one sentence: why this persona fits the segment>",
  "match_detail": "<one sentence: the specific accessibility challenges this persona will surface in the audit>"
}}"""


def _strip_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` wrappers the model may add."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def suggest_personas(app_id: str, app_name: str) -> list[dict]:
    """Call DeepSeek flash and return a list of persona suggestions. Returns [] on failure."""
    from app.config import settings
    from app.db import get_client

    if not settings.llm_api_key:
        logger.warning("LLM_API_KEY not set — skipping persona suggestion")
        return []

    client = get_client()

    demographics = (
        client.table("app_demographics")
        .select("label, description")
        .eq("app_id", app_id)
        .order("sort_order")
        .execute()
        .data or []
    )

    raw_personas = (
        client.table("personas")
        .select("slug, name, age_band, language, disabilities, tech_savviness")
        .order("created_at")
        .execute()
        .data or []
    )
    # Normalise to camelCase for the prompt helper
    personas = [
        {
            "slug": p["slug"],
            "name": p["name"],
            "ageBand": p.get("age_band", ""),
            "language": p.get("language", ""),
            "disabilities": p.get("disabilities") or [],
            "techSavviness": p.get("tech_savviness", 0.5),
        }
        for p in raw_personas
    ]

    prompt = _build_prompt(app_name, demographics, personas)

    try:
        from langchain_deepseek import ChatDeepSeek
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatDeepSeek(
            model=settings.llm_model_step,
            api_key=settings.llm_api_key,
            api_base=settings.llm_base_url,
            temperature=0.3,
            max_retries=1,
        )
        resp = llm.invoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ])
        raw = _strip_fences(resp.content.strip())
        suggestions: list[dict] = json.loads(raw)
        if not isinstance(suggestions, list):
            raise ValueError("LLM returned non-list JSON")
        return suggestions
    except Exception as exc:
        logger.warning("Persona suggestion failed for app %s: %s", app_id, exc)
        return []
