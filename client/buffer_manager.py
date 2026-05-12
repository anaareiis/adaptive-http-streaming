"""Buffer management for adaptive streaming."""

from typing import List, Dict, Optional
from datetime import datetime


class BufferManager:
    """Manages video buffer for streaming playback."""

    # Constants for buffer management
    MIN_BUFFER_TO_PLAY = 2.0  # Minimum buffer in seconds to start playback
    REBUFFER_THRESHOLD = 0.0  # Buffer level that triggers rebuffering

    def __init__(self, max_buffer: float = 60.0):
        """
        Initialize the buffer manager.

        Args:
            max_buffer: Maximum buffer capacity in seconds (default: 60s)
        """
        if max_buffer <= 0:
            raise ValueError("max_buffer must be positive")

        self.max_buffer = max_buffer
        self.current_buffer = 0.0
        self.rebuffer_count = 0
        self.rebuffer_history = []
        self.total_consumed = 0.0

    def add_segment(self, duration: float) -> None:
        """
        Add a segment to the buffer.

        Args:
            duration: Duration of the segment in seconds

        Raises:
            ValueError: If duration is not positive
        """
        if duration <= 0:
            raise ValueError("Segment duration must be positive")

        # Add segment to buffer, capped at max_buffer
        old_buffer = self.current_buffer
        self.current_buffer = min(self.current_buffer + duration, self.max_buffer)

        # Check if this addition caused buffer overflow
        if self.current_buffer == self.max_buffer and old_buffer < self.max_buffer:
            pass  # Buffer is now full, no issue

    def consume(self, time_elapsed: float) -> None:
        """
        Consume buffer during playback.

        Args:
            time_elapsed: Time elapsed in seconds

        Raises:
            ValueError: If time_elapsed is not positive
        """
        if time_elapsed <= 0:
            raise ValueError("time_elapsed must be positive")

        old_buffer = self.current_buffer
        self.current_buffer = max(0.0, self.current_buffer - time_elapsed)
        self.total_consumed += time_elapsed

        # Detect rebuffering: when buffer goes from > 0 to <= 0
        if old_buffer > self.REBUFFER_THRESHOLD and self.current_buffer <= self.REBUFFER_THRESHOLD:
            self._record_rebuffer()

    def can_play(self) -> bool:
        """
        Check if there's enough buffer to continue playback.

        Returns:
            True if buffer >= MIN_BUFFER_TO_PLAY, False otherwise
        """
        return self.current_buffer >= self.MIN_BUFFER_TO_PLAY

    def get_buffer_level(self) -> float:
        """
        Get current buffer level in seconds.

        Returns:
            Current buffer duration in seconds
        """
        return self.current_buffer

    def get_buffer_percentage(self) -> float:
        """
        Get buffer as percentage of max capacity.

        Returns:
            Percentage (0-100) of buffer utilization
        """
        if self.max_buffer == 0:
            return 0.0
        return (self.current_buffer / self.max_buffer) * 100

    def _record_rebuffer(self) -> None:
        """Record a rebuffering event."""
        self.rebuffer_count += 1
        event = {
            "timestamp": datetime.now(),
            "buffer_level": self.current_buffer,
            "rebuffer_number": self.rebuffer_count,
        }
        self.rebuffer_history.append(event)

    def get_rebuffer_count(self) -> int:
        """
        Get total number of rebuffering events.

        Returns:
            Number of times rebuffering occurred
        """
        return self.rebuffer_count

    def get_rebuffer_history(self) -> List[Dict]:
        """
        Get complete rebuffering history.

        Returns:
            List of rebuffering events with timestamp and details
        """
        return self.rebuffer_history.copy()

    def get_last_rebuffer(self) -> Optional[Dict]:
        """
        Get the last rebuffering event.

        Returns:
            Last rebuffer event or None if never rebuffered
        """
        if self.rebuffer_history:
            return self.rebuffer_history[-1].copy()
        return None

    def is_rebuffering(self) -> bool:
        """
        Check if currently in rebuffering state.

        A stream is in rebuffering state when:
        - Buffer is exhausted (<=0)
        - AND we have attempted playback (rebuffer_count > 0 or total_consumed > 0)

        Returns:
            True if in rebuffering state
        """
        return (
            self.current_buffer <= self.REBUFFER_THRESHOLD
            and (self.rebuffer_count > 0 or self.total_consumed > 0)
        )

    def fill_buffer(self, duration: float) -> None:
        """
        Fill buffer with multiple segments rapidly (for testing/simulation).

        Args:
            duration: Total duration to add in seconds
        """
        if duration <= 0:
            raise ValueError("duration must be positive")

        self.current_buffer = min(self.current_buffer + duration, self.max_buffer)

    def drain_buffer(self, duration: float) -> None:
        """
        Drain buffer (for testing/simulation).

        Args:
            duration: Duration to drain in seconds
        """
        if duration <= 0:
            raise ValueError("duration must be positive")

        old_buffer = self.current_buffer
        self.current_buffer = max(0.0, self.current_buffer - duration)

        # Check for rebuffering
        if old_buffer > self.REBUFFER_THRESHOLD and self.current_buffer <= self.REBUFFER_THRESHOLD:
            self._record_rebuffer()

    def reset(self) -> None:
        """Reset buffer to empty state and clear history."""
        self.current_buffer = 0.0
        self.rebuffer_count = 0
        self.rebuffer_history = []
        self.total_consumed = 0.0

    def get_stats(self) -> Dict:
        """
        Get comprehensive buffer statistics.

        Returns:
            Dictionary with buffer metrics
        """
        return {
            "current_buffer": self.current_buffer,
            "max_buffer": self.max_buffer,
            "buffer_percentage": self.get_buffer_percentage(),
            "can_play": self.can_play(),
            "is_rebuffering": self.is_rebuffering(),
            "rebuffer_count": self.rebuffer_count,
            "total_consumed": self.total_consumed,
        }

    def __repr__(self) -> str:
        """Return string representation of buffer manager."""
        return (
            f"BufferManager(buffer={self.current_buffer:.1f}s/"
            f"{self.max_buffer:.1f}s, "
            f"rebuffers={self.rebuffer_count}, "
            f"can_play={self.can_play()})"
        )
