"""Scoring engine (§16). Pure, seeded, unit-tested. The defensible IP."""
from app.scoring.engine import ScoreWeights, StepSignals, WcagSignal, score

__all__ = ["score", "ScoreWeights", "StepSignals", "WcagSignal"]
