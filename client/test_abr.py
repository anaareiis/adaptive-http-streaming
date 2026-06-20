"""Tests for the Rate-Based ABR algorithm."""

import pytest
from datetime import datetime
from abr import RateBasedABR, HybridABR


SAMPLE_QUALITIES = [
    {"name": "240p", "bitrate": 200},
    {"name": "360p", "bitrate": 400},
    {"name": "480p", "bitrate": 800},
    {"name": "720p", "bitrate": 1200},
    {"name": "1080p", "bitrate": 2500},
]


class TestRateBasedABR:
    """Test cases for RateBasedABR algorithm."""

    def test_initialization(self):
        """Test ABR algorithm initialization."""
        abr = RateBasedABR()

        assert abr.current_quality is None
        assert abr.decision_history == []
        assert abr.SAFETY_FACTOR == 0.85

    def test_select_quality_high_throughput(self):
        """Test quality selection with high throughput."""
        abr = RateBasedABR()

        # 1400 kbps * 0.85 = 1190 kbps → can reach 480p but not 720p
        quality = abr.select_quality(1400, SAMPLE_QUALITIES)

        assert quality == "480p"

    def test_select_quality_low_throughput(self):
        """Test quality selection with low throughput."""
        abr = RateBasedABR()

        # 250 kbps * 0.85 = 212.5 kbps → only 240p fits
        quality = abr.select_quality(250, SAMPLE_QUALITIES)

        assert quality == "240p"

    def test_select_quality_medium_throughput(self):
        """Test quality selection with medium throughput."""
        abr = RateBasedABR()

        # 500 kbps * 0.85 = 425 kbps → up to 360p fits
        quality = abr.select_quality(500, SAMPLE_QUALITIES)

        assert quality == "360p"

    def test_select_quality_very_high_throughput(self):
        """Test quality selection with very high throughput."""
        abr = RateBasedABR()

        # 3000 kbps * 0.85 = 2550 kbps → 1080p fits
        quality = abr.select_quality(3000, SAMPLE_QUALITIES)

        assert quality == "1080p"

    def test_select_quality_very_low_throughput(self):
        """Test quality selection with very low throughput (fallback)."""
        abr = RateBasedABR()

        # 100 kbps * 0.85 = 85 kbps → nothing fits, use minimum (240p)
        quality = abr.select_quality(100, SAMPLE_QUALITIES)

        assert quality == "240p"

    def test_select_quality_updates_current(self):
        """Test that current_quality is updated after selection."""
        abr = RateBasedABR()

        abr.select_quality(500, SAMPLE_QUALITIES)
        assert abr.current_quality == "360p"

        abr.select_quality(1400, SAMPLE_QUALITIES)
        assert abr.current_quality == "480p"

    def test_decision_history_recorded(self):
        """Test that decisions are recorded in history."""
        abr = RateBasedABR()

        abr.select_quality(500, SAMPLE_QUALITIES)
        abr.select_quality(1400, SAMPLE_QUALITIES)

        assert len(abr.decision_history) == 2
        assert abr.decision_history[0]["selected_quality"] == "360p"
        assert abr.decision_history[1]["selected_quality"] == "480p"

    def test_decision_history_structure(self):
        """Test that decision history has correct structure."""
        abr = RateBasedABR()

        abr.select_quality(500, SAMPLE_QUALITIES)
        decision = abr.decision_history[0]

        assert "timestamp" in decision
        assert "throughput_kbps" in decision
        assert "safety_limit_kbps" in decision
        assert "selected_quality" in decision

    def test_get_last_decision(self):
        """Test retrieving last decision."""
        abr = RateBasedABR()

        # No decisions yet
        assert abr.get_last_decision() is None

        abr.select_quality(500, SAMPLE_QUALITIES)
        last = abr.get_last_decision()

        assert last["selected_quality"] == "360p"
        assert last["throughput_kbps"] == 500

    def test_get_decision_count_total(self):
        """Test getting total decision count."""
        abr = RateBasedABR()

        abr.select_quality(500, SAMPLE_QUALITIES)
        abr.select_quality(1400, SAMPLE_QUALITIES)
        abr.select_quality(250, SAMPLE_QUALITIES)

        assert abr.get_decision_count() == 3

    def test_get_decision_count_by_quality(self):
        """Test counting decisions for specific quality."""
        abr = RateBasedABR()

        abr.select_quality(500, SAMPLE_QUALITIES)  # 360p
        abr.select_quality(1400, SAMPLE_QUALITIES)  # 480p
        abr.select_quality(500, SAMPLE_QUALITIES)  # 360p
        abr.select_quality(3000, SAMPLE_QUALITIES)  # 1080p

        assert abr.get_decision_count("360p") == 2
        assert abr.get_decision_count("480p") == 1
        assert abr.get_decision_count("1080p") == 1
        assert abr.get_decision_count("240p") == 0

    def test_get_quality_switches(self):
        """Test detecting quality switches."""
        abr = RateBasedABR()

        abr.select_quality(500, SAMPLE_QUALITIES)  # 360p
        abr.select_quality(500, SAMPLE_QUALITIES)  # 360p (no switch)
        abr.select_quality(1400, SAMPLE_QUALITIES)  # 480p (switch)
        abr.select_quality(250, SAMPLE_QUALITIES)  # 240p (switch)

        switches = abr.get_quality_switches()

        assert len(switches) == 2
        assert switches[0]["from_quality"] == "360p"
        assert switches[0]["to_quality"] == "480p"
        assert switches[1]["from_quality"] == "480p"
        assert switches[1]["to_quality"] == "240p"

    def test_reset_history(self):
        """Test resetting decision history."""
        abr = RateBasedABR()

        abr.select_quality(500, SAMPLE_QUALITIES)
        abr.select_quality(1400, SAMPLE_QUALITIES)

        assert len(abr.decision_history) == 2

        abr.reset_history()

        assert len(abr.decision_history) == 0
        assert abr.current_quality is None

    def test_invalid_throughput_type(self):
        """Test error when throughput is not numeric."""
        abr = RateBasedABR()

        with pytest.raises(TypeError):
            abr.select_quality("500", SAMPLE_QUALITIES)

        with pytest.raises(TypeError):
            abr.select_quality(None, SAMPLE_QUALITIES)

    def test_empty_qualities_list(self):
        """Test error when qualities list is empty."""
        abr = RateBasedABR()

        with pytest.raises(ValueError):
            abr.select_quality(500, [])

    def test_invalid_quality_format(self):
        """Test error with invalid quality format."""
        abr = RateBasedABR()

        invalid_qualities = [
            {"name": "240p"},  # Missing bitrate
            {"bitrate": 400},  # Missing name
        ]

        with pytest.raises(ValueError):
            abr.select_quality(500, invalid_qualities)

    def test_single_quality(self):
        """Test with only one quality available."""
        abr = RateBasedABR()

        qualities = [{"name": "480p", "bitrate": 800}]

        # Should always select the only option
        quality = abr.select_quality(500, qualities)
        assert quality == "480p"

        quality = abr.select_quality(1000, qualities)
        assert quality == "480p"

        quality = abr.select_quality(100, qualities)
        assert quality == "480p"

    def test_safety_factor_applied(self):
        """Test that safety factor is correctly applied."""
        abr = RateBasedABR()

        # At exactly the bitrate * safety_factor boundary
        # 400 * 0.85 = 340, so 360p (400 kbps) should NOT fit
        quality = abr.select_quality(400, SAMPLE_QUALITIES)
        assert quality == "240p"

        # Just above the boundary (need 400 / 0.85 = 470.588...)
        quality = abr.select_quality(471, SAMPLE_QUALITIES)  # 471 * 0.85 = 400.35
        assert quality == "360p"

    def test_repr(self):
        """Test string representation of ABR."""
        abr = RateBasedABR()

        repr_str = repr(abr)
        assert "RateBasedABR" in repr_str
        assert "current_quality=None" in repr_str
        assert "decisions=0" in repr_str

        abr.select_quality(500, SAMPLE_QUALITIES)
        repr_str = repr(abr)

        assert "current_quality=360p" in repr_str
        assert "decisions=1" in repr_str


class TestHybridABR:
    """Test cases for HybridABR (Política 3) algorithm."""

    def test_initialization(self):
        """Test ABR algorithm initialization."""
        abr = HybridABR()

        assert abr.current_quality is None
        assert abr.decision_history == []
        assert abr.ewma_throughput is None

    def test_empty_qualities_raises(self):
        """Test that an empty qualities list raises ValueError."""
        abr = HybridABR()

        with pytest.raises(ValueError):
            abr.select_quality(1000, 10.0, 20.0, [])

    def test_first_decision_uses_raw_throughput(self):
        """Test that the EWMA starts at the first measured throughput."""
        abr = HybridABR()

        abr.select_quality(1500, jitter_ms=0.0, buffer_level_s=20.0, qualities=SAMPLE_QUALITIES)

        assert abr.ewma_throughput == 1500

    def test_ewma_smooths_throughput_over_time(self):
        """Test that EWMA blends new samples with the running average instead
        of jumping straight to the latest value."""
        abr = HybridABR()

        abr.select_quality(1000, jitter_ms=0.0, buffer_level_s=20.0, qualities=SAMPLE_QUALITIES)
        abr.select_quality(3000, jitter_ms=0.0, buffer_level_s=20.0, qualities=SAMPLE_QUALITIES)

        # EWMA_ALPHA = 0.3 -> 0.3*3000 + 0.7*1000 = 1600
        assert abr.ewma_throughput == pytest.approx(1600.0)

    def test_high_jitter_penalizes_quality(self):
        """Test that high jitter forces a lower quality than low jitter at the
        same throughput — the explicit jitter handling required by Tarefa 3."""
        low_jitter_abr = HybridABR()
        high_jitter_abr = HybridABR()

        # Same throughput, healthy buffer in both cases — only jitter differs.
        low_jitter_quality = low_jitter_abr.select_quality(
            1500, jitter_ms=5.0, buffer_level_s=30.0, qualities=SAMPLE_QUALITIES
        )
        high_jitter_quality = high_jitter_abr.select_quality(
            1500, jitter_ms=300.0, buffer_level_s=30.0, qualities=SAMPLE_QUALITIES
        )

        qualities_order = [q["name"] for q in sorted(SAMPLE_QUALITIES, key=lambda q: q["bitrate"])]
        assert qualities_order.index(high_jitter_quality) < qualities_order.index(low_jitter_quality)

    def test_buffer_safety_net_forces_minimum_quality(self):
        """Test that a critically low buffer forces the minimum quality even
        when throughput is high and jitter is low."""
        abr = HybridABR()

        quality = abr.select_quality(
            5000, jitter_ms=0.0, buffer_level_s=2.0, qualities=SAMPLE_QUALITIES
        )

        assert quality == "240p"

    def test_decision_history_tracking(self):
        """Test that decisions are recorded with the expected fields."""
        abr = HybridABR()

        abr.select_quality(1500, jitter_ms=10.0, buffer_level_s=20.0, qualities=SAMPLE_QUALITIES)
        history = abr.get_decision_history()

        assert len(history) == 1
        decision = history[0]
        assert "ewma_throughput_kbps" in decision
        assert "penalty" in decision
        assert "effective_throughput_kbps" in decision
        assert decision["selected_quality"] == abr.current_quality

    def test_quality_switches(self):
        """Test detection of quality switches across decisions."""
        abr = HybridABR()

        abr.select_quality(200, jitter_ms=0.0, buffer_level_s=20.0, qualities=SAMPLE_QUALITIES)
        abr.select_quality(5000, jitter_ms=0.0, buffer_level_s=20.0, qualities=SAMPLE_QUALITIES)

        switches = abr.get_quality_switches()
        assert len(switches) == 1
        assert switches[0]["from_quality"] != switches[0]["to_quality"]

    def test_reset_history(self):
        """Test that reset clears history, current quality and the EWMA state."""
        abr = HybridABR()
        abr.select_quality(1500, jitter_ms=10.0, buffer_level_s=20.0, qualities=SAMPLE_QUALITIES)

        abr.reset_history()

        assert abr.decision_history == []
        assert abr.current_quality is None
        assert abr.ewma_throughput is None

    def test_repr(self):
        """Test string representation of ABR."""
        abr = HybridABR()

        repr_str = repr(abr)
        assert "HybridABR" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
