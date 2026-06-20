"""Shared LLM usage accounting utilities.

Tracks prompt/completion tokens and (optionally) estimated cost for every
DeepSeek call made during a run. The tracker is intentionally lightweight so it
can be used from sync routes as well as worker threads spawned by the streaming
endpoint.

The public helpers are:

    track_usage(on_update=None) -> context manager returning the tracker
    set_tracker(tracker | None)
    current_tracker() -> LLMUsageTracker | None
    record_usage(model: str, prompt_tokens: int | None, completion_tokens: int | None)

`record_usage` is safe to call even when no tracker is active; this keeps the
LLM call sites simple.
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from app.config import settings


def _parse_pricing() -> dict[str, dict[str, float]]:
    raw = settings.llm_pricing
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    parsed: dict[str, dict[str, float]] = {}
    for model, entry in data.items():
        if not isinstance(entry, dict):
            continue
        try:
            prompt = float(entry.get("prompt", 0))
            completion = float(entry.get("completion", 0))
        except (TypeError, ValueError):
            continue
        parsed[model] = {"prompt": max(prompt, 0.0), "completion": max(completion, 0.0)}
    return parsed


PRICING_TABLE = _parse_pricing()


@dataclass
class ModelUsage:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    pricing_applied: bool = False

    def add(self, prompt: int, completion: int, cost: float, priced: bool) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.cost += cost
        self.pricing_applied = self.pricing_applied or priced

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class UsageSummary:
    currency: str
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost: float
    pricing_applied: bool
    models: list[ModelUsage] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens


class LLMUsageTracker:
    def __init__(self) -> None:
        self._models: Dict[str, ModelUsage] = {}
        self._total_prompt = 0
        self._total_completion = 0
        self._total_cost = 0.0
        self._pricing_applied = False
        self._on_update: Optional[Callable[[dict], None]] = None
        self._last_serialized: Optional[dict] = None

    def set_callback(self, callback: Optional[Callable[[dict], None]]) -> None:
        self._on_update = callback

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return

        prompt = max(prompt_tokens, 0)
        completion = max(completion_tokens, 0)

        pricing = PRICING_TABLE.get(model)
        priced = False
        model_cost = 0.0
        if pricing:
            priced = True
            prompt_cost = pricing.get("prompt", 0.0) * (prompt / 1000.0)
            completion_cost = pricing.get("completion", 0.0) * (completion / 1000.0)
            model_cost = prompt_cost + completion_cost

        usage = self._models.setdefault(model, ModelUsage(model=model))
        usage.add(prompt, completion, model_cost, priced)

        self._total_prompt += prompt
        self._total_completion += completion
        self._total_cost += model_cost
        if priced:
            self._pricing_applied = True

        if self._on_update:
            payload = self.serialized()
            if payload != self._last_serialized:
                self._last_serialized = payload
                self._on_update(payload)

    def summary(self) -> UsageSummary:
        return UsageSummary(
            currency=settings.llm_pricing_currency,
            total_prompt_tokens=self._total_prompt,
            total_completion_tokens=self._total_completion,
            total_cost=self._total_cost,
            pricing_applied=self._pricing_applied,
            models=list(self._models.values()),
        )

    def serialized(self) -> dict:
        summary = self.summary()
        return {
            "currency": summary.currency,
            "total_prompt_tokens": summary.total_prompt_tokens,
            "total_completion_tokens": summary.total_completion_tokens,
            "total_tokens": summary.total_tokens,
            "total_cost": summary.total_cost,
            "pricing_applied": summary.pricing_applied,
            "models": [
                {
                    "model": m.model,
                    "prompt_tokens": m.prompt_tokens,
                    "completion_tokens": m.completion_tokens,
                    "total_tokens": m.total_tokens,
                    "cost": m.cost,
                    "pricing_applied": m.pricing_applied,
                }
                for m in summary.models
            ],
        }


_STATE = threading.local()


def set_tracker(tracker: Optional[LLMUsageTracker]) -> None:
    _STATE.tracker = tracker


def current_tracker() -> Optional[LLMUsageTracker]:
    return getattr(_STATE, "tracker", None)


@contextmanager
def track_usage(on_update: Optional[Callable[[dict], None]] = None):  # noqa: D401 - context manager
    tracker = LLMUsageTracker()
    tracker.set_callback(on_update)
    previous = current_tracker()
    set_tracker(tracker)
    try:
        yield tracker
    finally:
        set_tracker(previous)


def record_usage(model: str, prompt_tokens: Optional[int], completion_tokens: Optional[int]) -> None:
    tracker = current_tracker()
    if tracker is None:
        return
    tracker.record(model, prompt_tokens or 0, completion_tokens or 0)
