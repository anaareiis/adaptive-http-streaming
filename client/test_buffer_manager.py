"""Tests for the BufferManager."""

import pytest
from datetime import datetime
from buffer_manager import BufferManager


class TestBufferManagerBasics:
    """Test basic buffer operations."""

    def test_initialization(self):
        """Test buffer manager initialization."""
        bm = BufferManager(max_buffer=60.0)

        assert bm.current_buffer == 0.0
        assert bm.max_buffer == 60.0
        assert bm.rebuffer_count == 0
        assert bm.MIN_BUFFER_TO_PLAY == 2.0

    def test_invalid_max_buffer(self):
        """Test error with invalid max_buffer."""
        with pytest.raises(ValueError):
            BufferManager(max_buffer=0)

        with pytest.raises(ValueError):
            BufferManager(max_buffer=-10)

    def test_add_segment(self):
        """Test adding segments to buffer."""
        bm = BufferManager(max_buffer=60.0)

        bm.add_segment(4.0)
        assert bm.current_buffer == 4.0

        bm.add_segment(4.0)
        assert bm.current_buffer == 8.0

    def test_add_segment_invalid_duration(self):
        """Test error with invalid segment duration."""
        bm = BufferManager()

        with pytest.raises(ValueError):
            bm.add_segment(0)

        with pytest.raises(ValueError):
            bm.add_segment(-1)

    def test_consume_buffer(self):
        """Test consuming buffer during playback."""
        bm = BufferManager()

        bm.add_segment(10.0)
        assert bm.current_buffer == 10.0

        bm.consume(3.0)
        assert bm.current_buffer == 7.0

        bm.consume(2.0)
        assert bm.current_buffer == 5.0

    def test_consume_invalid_time(self):
        """Test error with invalid time_elapsed."""
        bm = BufferManager()

        with pytest.raises(ValueError):
            bm.consume(0)

        with pytest.raises(ValueError):
            bm.consume(-1)

    def test_buffer_cannot_be_negative(self):
        """Test that buffer never goes negative."""
        bm = BufferManager()

        bm.add_segment(5.0)
        bm.consume(10.0)  # Try to consume more than available

        assert bm.current_buffer == 0.0

    def test_buffer_capped_at_max(self):
        """Test that buffer is capped at max_buffer."""
        bm = BufferManager(max_buffer=20.0)

        bm.add_segment(15.0)
        assert bm.current_buffer == 15.0

        bm.add_segment(10.0)  # Would exceed max, should be capped
        assert bm.current_buffer == 20.0


class TestBufferPlayability:
    """Test buffer playability checks."""

    def test_can_play_sufficient_buffer(self):
        """Test playability with sufficient buffer."""
        bm = BufferManager()

        bm.add_segment(10.0)
        assert bm.can_play() is True

    def test_can_play_threshold(self):
        """Test playability at threshold (2 seconds)."""
        bm = BufferManager()

        # Exactly at threshold
        bm.add_segment(2.0)
        assert bm.can_play() is True

        # Just below threshold
        bm.consume(0.1)
        assert bm.can_play() is False

    def test_can_play_empty_buffer(self):
        """Test playability with empty buffer."""
        bm = BufferManager()

        assert bm.can_play() is False

    def test_playback_scenario(self):
        """Test realistic playback scenario."""
        bm = BufferManager()

        # Start with empty buffer - can't play
        assert bm.can_play() is False

        # Download first segment
        bm.add_segment(4.0)
        assert bm.can_play() is True

        # Download second segment
        bm.add_segment(4.0)
        assert bm.current_buffer == 8.0

        # Playback for 3 seconds
        bm.consume(3.0)
        assert bm.current_buffer == 5.0
        assert bm.can_play() is True


class TestRebuffering:
    """Test rebuffering detection."""

    def test_no_rebuffer_on_playback(self):
        """Test that normal playback doesn't trigger rebuffering."""
        bm = BufferManager()

        bm.add_segment(10.0)
        bm.consume(5.0)
        bm.consume(3.0)

        assert bm.get_rebuffer_count() == 0

    def test_rebuffer_on_buffer_exhaustion(self):
        """Test rebuffering when buffer is exhausted."""
        bm = BufferManager()

        bm.add_segment(5.0)
        bm.consume(5.1)  # Consume more than available

        assert bm.get_rebuffer_count() == 1
        assert bm.current_buffer == 0.0

    def test_rebuffer_history(self):
        """Test rebuffering history recording."""
        bm = BufferManager()

        # First rebuffer
        bm.add_segment(5.0)
        bm.consume(6.0)

        # Second rebuffer
        bm.add_segment(3.0)
        bm.consume(4.0)

        history = bm.get_rebuffer_history()

        assert len(history) == 2
        assert history[0]["rebuffer_number"] == 1
        assert history[1]["rebuffer_number"] == 2

    def test_get_last_rebuffer(self):
        """Test getting last rebuffer event."""
        bm = BufferManager()

        # No rebuffers yet
        assert bm.get_last_rebuffer() is None

        # Create rebuffer
        bm.add_segment(5.0)
        bm.consume(6.0)

        last = bm.get_last_rebuffer()
        assert last is not None
        assert last["rebuffer_number"] == 1

    def test_is_rebuffering(self):
        """Test rebuffering state check."""
        bm = BufferManager()

        # Empty buffer at start is not considered "rebuffering"
        # It's just not ready to play yet
        assert bm.is_rebuffering() is False

        # Add buffer to allow playback
        bm.add_segment(3.0)
        assert bm.is_rebuffering() is False

        # Exhaust buffer during playback
        bm.consume(3.1)

        # Now rebuffering
        assert bm.is_rebuffering() is True

        # Add buffer to recover
        bm.add_segment(3.0)
        assert bm.is_rebuffering() is False

    def test_no_duplicate_rebuffer_event(self):
        """Test that consecutive consume calls don't create duplicate events."""
        bm = BufferManager()

        bm.add_segment(1.0)
        bm.consume(0.5)
        bm.consume(0.3)
        bm.consume(0.3)  # Should trigger rebuffer

        # Should only have 1 rebuffer event
        assert bm.get_rebuffer_count() == 1


class TestBufferMetrics:
    """Test buffer metrics and statistics."""

    def test_get_buffer_level(self):
        """Test getting current buffer level."""
        bm = BufferManager()

        bm.add_segment(5.0)
        assert bm.get_buffer_level() == 5.0

        bm.consume(2.0)
        assert bm.get_buffer_level() == 3.0

    def test_get_buffer_percentage(self):
        """Test buffer percentage calculation."""
        bm = BufferManager(max_buffer=100.0)

        bm.add_segment(50.0)
        assert bm.get_buffer_percentage() == 50.0

        bm.add_segment(30.0)
        assert bm.get_buffer_percentage() == 80.0

        bm.add_segment(30.0)  # Would be 110, capped at 100
        assert bm.get_buffer_percentage() == 100.0

    def test_get_stats(self):
        """Test comprehensive statistics."""
        bm = BufferManager(max_buffer=60.0)

        bm.add_segment(10.0)
        bm.consume(3.0)

        stats = bm.get_stats()

        assert stats["current_buffer"] == 7.0
        assert stats["max_buffer"] == 60.0
        assert stats["buffer_percentage"] > 0
        assert stats["can_play"] is True
        assert stats["is_rebuffering"] is False
        assert stats["rebuffer_count"] == 0

    def test_total_consumed(self):
        """Test total consumed tracking."""
        bm = BufferManager()

        bm.add_segment(20.0)
        bm.consume(5.0)
        bm.consume(3.0)
        bm.consume(2.0)

        assert bm.total_consumed == 10.0


class TestBufferOperations:
    """Test utility buffer operations."""

    def test_fill_buffer(self):
        """Test fill_buffer utility."""
        bm = BufferManager(max_buffer=30.0)

        bm.fill_buffer(20.0)
        assert bm.current_buffer == 20.0

        bm.fill_buffer(20.0)  # Would exceed, should cap
        assert bm.current_buffer == 30.0

    def test_drain_buffer(self):
        """Test drain_buffer utility."""
        bm = BufferManager()

        bm.fill_buffer(10.0)
        bm.drain_buffer(3.0)

        assert bm.current_buffer == 7.0

    def test_drain_triggers_rebuffer(self):
        """Test that drain_buffer triggers rebuffering."""
        bm = BufferManager()

        bm.fill_buffer(2.0)
        bm.drain_buffer(2.1)

        assert bm.get_rebuffer_count() == 1

    def test_reset(self):
        """Test buffer reset."""
        bm = BufferManager()

        bm.add_segment(10.0)
        bm.consume(5.1)  # Trigger rebuffer

        bm.reset()

        assert bm.current_buffer == 0.0
        assert bm.rebuffer_count == 0
        assert bm.rebuffer_history == []
        assert bm.total_consumed == 0.0

    def test_repr(self):
        """Test string representation."""
        bm = BufferManager(max_buffer=60.0)

        repr_str = repr(bm)
        assert "BufferManager" in repr_str
        assert "buffer=0.0s/60.0s" in repr_str
        assert "rebuffers=0" in repr_str

        bm.add_segment(30.0)
        repr_str = repr(bm)
        assert "can_play=True" in repr_str


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_buffer_max(self):
        """Test with very small max buffer."""
        bm = BufferManager(max_buffer=0.1)

        bm.add_segment(0.05)
        assert bm.current_buffer == 0.05

        bm.add_segment(0.1)
        assert bm.current_buffer == 0.1  # Capped

    def test_very_large_buffer_max(self):
        """Test with very large max buffer."""
        bm = BufferManager(max_buffer=3600.0)  # 1 hour

        bm.add_segment(1800.0)
        assert bm.current_buffer == 1800.0
        assert bm.get_buffer_percentage() == 50.0

    def test_multiple_rapid_segments(self):
        """Test adding multiple segments rapidly."""
        bm = BufferManager(max_buffer=50.0)

        for i in range(13):  # 13 * 4 = 52, exceeds 50
            bm.add_segment(4.0)

        assert bm.current_buffer == 50.0  # Capped

    def test_continuous_playback(self):
        """Test continuous playback scenario."""
        bm = BufferManager(max_buffer=30.0)

        for second in range(100):
            # Every 4 seconds, download a segment
            if second % 4 == 0:
                bm.add_segment(4.0)

            # Consume 1 second per iteration
            bm.consume(1.0)

            # Should not rebuffer often in this scenario
            if second < 50:  # First 50 seconds
                # Buffer should stay healthy
                assert bm.current_buffer >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
