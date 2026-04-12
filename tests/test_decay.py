"""Tests for the probabilistic decay functions."""

from datetime import datetime, timedelta, timezone

from engram.core.decay import (
    compute_confidence,
    reinforce,
    should_garbage_collect,
    time_until_threshold,
)


def _now():
    return datetime.now(timezone.utc)


class TestComputeConfidence:
    def test_no_time_elapsed(self):
        now = _now()
        conf = compute_confidence(1.0, created_at=now, half_life=timedelta(days=7), now=now)
        assert conf == 1.0

    def test_one_half_life(self):
        now = _now()
        created = now - timedelta(days=7)
        conf = compute_confidence(1.0, created_at=created, half_life=timedelta(days=7), now=now)
        assert abs(conf - 0.5) < 0.01

    def test_two_half_lives(self):
        now = _now()
        created = now - timedelta(days=14)
        conf = compute_confidence(1.0, created_at=created, half_life=timedelta(days=7), now=now)
        assert abs(conf - 0.25) < 0.01

    def test_initial_confidence_scales(self):
        now = _now()
        created = now - timedelta(days=7)
        conf = compute_confidence(0.8, created_at=created, half_life=timedelta(days=7), now=now)
        assert abs(conf - 0.4) < 0.01

    def test_reinforcement_slows_decay(self):
        now = _now()
        created = now - timedelta(days=7)

        without = compute_confidence(1.0, created_at=created, half_life=timedelta(days=7), reinforcement_count=0, now=now)
        with_reinforcement = compute_confidence(1.0, created_at=created, half_life=timedelta(days=7), reinforcement_count=5, now=now)

        assert with_reinforcement > without

    def test_clamped_to_zero_one(self):
        now = _now()
        conf = compute_confidence(1.5, created_at=now, half_life=timedelta(days=7), now=now)
        assert conf == 1.0

    def test_very_old_memory_near_zero(self):
        now = _now()
        created = now - timedelta(days=365)
        conf = compute_confidence(1.0, created_at=created, half_life=timedelta(days=7), now=now)
        assert conf < 0.001

    def test_future_created_at(self):
        now = _now()
        created = now + timedelta(hours=1)
        conf = compute_confidence(0.9, created_at=created, half_life=timedelta(days=7), now=now)
        assert conf == 0.9


class TestReinforce:
    def test_basic_boost(self):
        result = reinforce(0.6, boost=0.2)
        assert abs(result - 0.68) < 0.01

    def test_already_at_one(self):
        result = reinforce(1.0, boost=0.2)
        assert result == 1.0

    def test_zero_confidence(self):
        result = reinforce(0.0, boost=0.2)
        assert abs(result - 0.2) < 0.01

    def test_full_boost(self):
        result = reinforce(0.5, boost=1.0)
        assert result == 1.0


class TestShouldGarbageCollect:
    def test_below_threshold(self):
        assert should_garbage_collect(0.01, threshold=0.05) is True

    def test_above_threshold(self):
        assert should_garbage_collect(0.1, threshold=0.05) is False

    def test_at_threshold(self):
        assert should_garbage_collect(0.05, threshold=0.05) is False


class TestTimeUntilThreshold:
    def test_basic(self):
        duration = time_until_threshold(1.0, timedelta(days=7), threshold=0.05)
        # 1.0 * 0.5^(t/7) = 0.05 => t/7 = log2(20) ~ 4.32 => t ~ 30.2 days
        assert 29 < duration.total_seconds() / 86400 < 31

    def test_already_below(self):
        duration = time_until_threshold(0.01, timedelta(days=7), threshold=0.05)
        assert duration == timedelta(0)

    def test_reinforcement_extends(self):
        without = time_until_threshold(1.0, timedelta(days=7), threshold=0.05, reinforcement_count=0)
        with_r = time_until_threshold(1.0, timedelta(days=7), threshold=0.05, reinforcement_count=3)
        assert with_r > without
