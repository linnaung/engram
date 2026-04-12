"""Probabilistic decay functions for Engram memories.

The core idea: memories fade over time unless reinforced.
Confidence follows exponential decay with a half-life,
modulated by how often the memory has been accessed.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


def compute_confidence(
    initial_confidence: float,
    created_at: datetime,
    half_life: timedelta,
    reinforcement_count: int = 0,
    now: datetime | None = None,
) -> float:
    """Compute current confidence of a memory using exponential decay.

    Formula:
        confidence(t) = C₀ × 0.5^(elapsed / half_life) × reinforcement_boost

    Reinforcement boost: each reinforcement multiplies half_life by 1.2,
    effectively slowing the decay. A memory referenced 5 times decays
    ~2.5x slower than one never referenced.

    Args:
        initial_confidence: Starting confidence (0.0 to 1.0).
        created_at: When the memory was created.
        half_life: Time for confidence to halve (without reinforcement).
        reinforcement_count: Number of times this memory was reinforced.
        now: Current time (defaults to UTC now).

    Returns:
        Current confidence value, clamped to [0.0, 1.0].
    """
    if now is None:
        now = datetime.now(timezone.utc)

    elapsed = now - created_at
    if elapsed.total_seconds() <= 0:
        return min(initial_confidence, 1.0)

    # Each reinforcement extends the effective half-life by 20%
    effective_half_life = half_life * (1.2 ** reinforcement_count)

    # Exponential decay
    if effective_half_life.total_seconds() <= 0:
        return 0.0

    decay_ratio = elapsed / effective_half_life
    confidence = initial_confidence * math.pow(0.5, decay_ratio)

    return max(0.0, min(1.0, confidence))


def reinforce(
    current_confidence: float,
    boost: float = 0.2,
) -> float:
    """Boost confidence when a memory is accessed or referenced.

    Moves confidence toward 1.0 by the boost fraction of the remaining gap.
    E.g., confidence=0.6, boost=0.2 → 0.6 + 0.2*(1.0-0.6) = 0.68

    Args:
        current_confidence: Current confidence value.
        boost: Fraction of the gap to 1.0 to recover (0.0 to 1.0).

    Returns:
        New confidence value, clamped to [0.0, 1.0].
    """
    gap = 1.0 - current_confidence
    new_confidence = current_confidence + boost * gap
    return max(0.0, min(1.0, new_confidence))


def should_garbage_collect(confidence: float, threshold: float = 0.05) -> bool:
    """Check if a memory has decayed below the garbage collection threshold."""
    return confidence < threshold


def time_until_threshold(
    initial_confidence: float,
    half_life: timedelta,
    threshold: float = 0.05,
    reinforcement_count: int = 0,
) -> timedelta:
    """Calculate how long until a memory decays below the threshold.

    Useful for showing users when a memory will be forgotten.
    """
    if initial_confidence <= threshold:
        return timedelta(0)

    effective_half_life = half_life * (1.2 ** reinforcement_count)

    # Solve: threshold = initial * 0.5^(t / half_life)
    # t = half_life * log2(initial / threshold)
    ratio = initial_confidence / threshold
    periods = math.log2(ratio)

    return effective_half_life * periods
