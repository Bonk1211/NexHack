"""Figurine image generation via DashScope wan2.7-image-pro.

Flow: POST /personas/{slug}/figurine
  → sets figurine_status = 'generating' in DB
  → kicks off BackgroundTask: generate_and_store(slug)
     → builds prompt from DB row
     → calls DashScope
     → downloads image bytes
     → uploads to Supabase Storage `figurine/{slug}.png`
     → sets figurine_status = 'ready', figurine_url = public URL
     → on any failure: figurine_status = 'failed'
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_LANGUAGE_FALLBACK = {
    "cantonese": "Chinese Malaysian with East Asian features",
    "mandarin": "Chinese Malaysian with East Asian features",
    "bahasa melayu": "Malay Malaysian",
    "tamil": "Indian Malaysian with South Asian features",
}

_ETHNICITY_SYSTEM = (
    "You infer ethnic appearance from a person's name for use in an image generation prompt. "
    "Reply with ONLY a short noun phrase (5-10 words) describing the likely ethnic appearance, "
    "e.g. 'Chinese Malaysian with East Asian features', 'Malay Malaysian', "
    "'Indian Malaysian with South Asian features', 'White Caucasian Western'. "
    "No explanation, no punctuation at the end, just the phrase."
)


def _ethnicity_from_name_llm(name: str) -> str | None:
    """Ask DeepSeek flash to infer ethnic appearance from name. Returns None on any failure."""
    from app.config import settings
    if not settings.llm_api_key:
        return None
    try:
        from langchain_deepseek import ChatDeepSeek
        from langchain_core.messages import HumanMessage, SystemMessage
        client = ChatDeepSeek(
            model=settings.llm_model_step,
            api_key=settings.llm_api_key,
            api_base=settings.llm_base_url,
            temperature=0,
            max_retries=1,
        )
        resp = client.invoke([
            SystemMessage(content=_ETHNICITY_SYSTEM),
            HumanMessage(content=f"Name: {name}"),
        ])
        result = resp.content.strip().strip(".")
        # Strip any "Name: " or "Name — " prefix the model may echo back
        if ":" in result:
            result = result.split(":", 1)[-1].strip()
        if "—" in result:
            result = result.split("—", 1)[-1].strip()
        return result if result else None
    except Exception as exc:
        logger.warning("LLM ethnicity inference failed for %s: %s", name, exc)
        return None


def _build_prompt(row: dict) -> str:
    name: str = row.get("name") or "a person"
    age_band: str = row.get("age_band") or "adult"
    language: str = row.get("language") or "English"
    disabilities: list = row.get("disabilities") or []
    tech: float = float(row.get("tech_savviness") or 0.5)
    label: str = row.get("label") or ""

    # Ethnicity: LLM infers from name, falls back to language mapping
    culture = _ethnicity_from_name_llm(name) or _LANGUAGE_FALLBACK.get(language.lower(), "Malaysian")

    # Tech savviness visual cues
    if tech < 0.35:
        tech_hint = "holds a simple feature phone, looks slightly uncertain"
    elif tech > 0.75:
        tech_hint = "confident posture, holds a sleek smartphone"
    else:
        tech_hint = "relaxed pose, holds a smartphone"

    # Disability visual cues
    disability_hints: list[str] = []
    seen: set[str] = set()

    def _add(hint: str) -> None:
        if hint not in seen:
            seen.add(hint)
            disability_hints.append(hint)

    for d in disabilities:
        d_low = d.lower()
        if "screen reader" in d_low or "low vision" in d_low:
            _add("wearing glasses with thick lenses")
        if "keyboard only" in d_low or "motor" in d_low:
            _add("seated, one hand resting on a keyboard")
        if "dyslexia" in d_low or "cognitive" in d_low:
            _add("thoughtful expression, book nearby")
        if "colour vision" in d_low:
            _add("wearing a subtle colour-blind friendly badge")
        if "hearing" in d_low:
            _add("wearing hearing aids")

    disability_str = ", ".join(disability_hints) if disability_hints else "approachable expression"

    label_note = f" ({label})" if label else ""

    return (
        f"A single cute collectible vinyl toy figurine of a {age_band} year old person "
        f"named {name}, {culture}. "
        f"Character: {disability_str}, {tech_hint}. "
        f"Style: Funko Pop inspired but softer and rounder — large round head, "
        f"small compact body, smooth plastic sheen, subtle cel-shading, "
        f"warm studio rim lighting. "
        f"Posed front-facing on a small circular display base. "
        f"Background: clean white seamless. "
        f"Render: high-quality 3D product photography, pastel muted tones, "
        f"soft shadows, collectible toy aesthetic. "
        f"Single figure, no text, no logos."
    )


def generate_and_store(slug: str, row: dict) -> None:
    """Run in a BackgroundTask — blocks until image is ready then writes to DB."""
    from app.db import get_client

    client = get_client()

    def _fail(reason: str) -> None:
        logger.error("figurine generation failed for %s: %s", slug, reason)
        client.table("personas").update({"figurine_status": "failed"}).eq("slug", slug).execute()

    if not settings.dashscope_api_key:
        _fail("DASHSCOPE_API_KEY not set")
        return

    import dashscope
    from dashscope.aigc.image_generation import ImageGeneration
    from dashscope.api_entities.dashscope_response import Message

    dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

    prompt = _build_prompt(row)
    logger.info("figurine prompt for %s: %s", slug, prompt[:120])

    try:
        rsp = ImageGeneration.call(
            model="wan2.7-image-pro",
            api_key=settings.dashscope_api_key,
            messages=[Message(role="user", content=[{"text": prompt}])],
            n=1,
        )
    except Exception as exc:
        _fail(f"DashScope call error: {exc}")
        return

    if rsp.status_code != 200:
        _fail(f"DashScope status {rsp.status_code}: {getattr(rsp, 'message', '')}")
        return

    # wan2.7-image-pro returns choices[0].message.content[0]['image']
    image_url: str | None = None
    try:
        choices = rsp.output.get("choices") or []
        if choices:
            content = choices[0].message.content or []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image":
                    image_url = item.get("image")
                    break
    except Exception as exc:
        _fail(f"URL extraction error: {exc}")
        return

    if not image_url:
        _fail("no image URL found in choices[0].message.content")
        return

    # Download image bytes
    try:
        img_bytes = httpx.get(image_url, timeout=60).content
    except Exception as exc:
        _fail(f"image download error: {exc}")
        return

    # Upload to Supabase Storage
    bucket = settings.figurine_bucket
    path = f"{slug}.png"
    try:
        client.storage.from_(bucket).upload(
            path=path,
            file=img_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
    except Exception as exc:
        _fail(f"storage upload error: {exc}")
        return

    # Public URL pattern for Supabase Storage
    public_url = f"{settings.supabase_url}/storage/v1/object/public/{bucket}/{path}"

    client.table("personas").update({
        "figurine_status": "ready",
        "figurine_url": public_url,
    }).eq("slug", slug).execute()

    logger.info("figurine ready for %s: %s", slug, public_url)
