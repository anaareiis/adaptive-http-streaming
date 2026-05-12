"""Metrics collection and analysis."""

import time
from collections import deque
from typing import List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ThroughputMeasurement:
    """Data class for a single throughput measurement."""

    bytes_downloaded: int
    time_elapsed: float
    throughput_kbps: float
    timestamp: datetime

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ThroughputMeasurement(throughput={self.throughput_kbps:.2f} kbps, bytes={self.bytes_downloaded})"


class ThroughputMeter:
    """Measure throughput (bitrate) of segment downloads."""

    def __init__(self, history_size: int = 5):
        """
        Initialize throughput meter.

        Args:
            history_size: Number of recent measurements to keep in history (default: 5)
        """
        self.history_size = history_size
        self.history: deque = deque(maxlen=history_size)
        self.current_start_time: Optional[float] = None
        self.current_start_timestamp: Optional[datetime] = None

    def start_measurement(self) -> None:
        """
        Start timing a download.

        Should be called before downloading a segment.
        """
        self.current_start_time = time.time()
        self.current_start_timestamp = datetime.now()

    def stop_measurement(self, bytes_downloaded: int) -> ThroughputMeasurement:
        """
        Stop timing and calculate throughput.

        Args:
            bytes_downloaded: Number of bytes downloaded in this segment

        Returns:
            ThroughputMeasurement object with calculated metrics

        Raises:
            RuntimeError: If start_measurement() was not called first
            ValueError: If bytes_downloaded is negative
        """
        if self.current_start_time is None:
            raise RuntimeError("Measurement not started. Call start_measurement() first.")

        if bytes_downloaded < 0:
            raise ValueError("bytes_downloaded must be non-negative")

        # Calculate elapsed time
        elapsed_time = time.time() - self.current_start_time

        # Avoid division by zero
        if elapsed_time <= 0:
            elapsed_time = 0.001  # 1 millisecond minimum

        # Calculate throughput: (bytes * 8 bits) / time in seconds / 1000 bits per kbit
        throughput_kbps = (bytes_downloaded * 8) / elapsed_time / 1000

        # Create measurement
        measurement = ThroughputMeasurement(
            bytes_downloaded=bytes_downloaded,
            time_elapsed=elapsed_time,
            throughput_kbps=throughput_kbps,
            timestamp=self.current_start_timestamp,
        )

        # Add to history
        self.history.append(measurement)

        # Reset
        self.current_start_time = None
        self.current_start_timestamp = None

        return measurement

    def get_history(self) -> List[ThroughputMeasurement]:
        """
        Get all measurements in history.

        Returns:
            List of ThroughputMeasurement objects
        """
        return list(self.history)

    def get_average_throughput(self) -> float:
        """
        Calculate average throughput from history.

        Returns:
            Average throughput in kbps

        Raises:
            RuntimeError: If history is empty
        """
        if not self.history:
            raise RuntimeError("No measurements in history")

        total = sum(m.throughput_kbps for m in self.history)
        return total / len(self.history)

    def get_min_throughput(self) -> float:
        """
        Get minimum throughput from history.

        Returns:
            Minimum throughput in kbps

        Raises:
            RuntimeError: If history is empty
        """
        if not self.history:
            raise RuntimeError("No measurements in history")

        return min(m.throughput_kbps for m in self.history)

    def get_max_throughput(self) -> float:
        """
        Get maximum throughput from history.

        Returns:
            Maximum throughput in kbps

        Raises:
            RuntimeError: If history is empty
        """
        if not self.history:
            raise RuntimeError("No measurements in history")

        return max(m.throughput_kbps for m in self.history)

    def get_jitter(self) -> float:
        """
        Calculate jitter (variation) in throughput.

        Jitter is the standard deviation of throughput values.

        Returns:
            Standard deviation of throughput in kbps

        Raises:
            RuntimeError: If history has less than 2 measurements
        """
        if len(self.history) < 2:
            raise RuntimeError("Need at least 2 measurements to calculate jitter")

        # Calculate average
        avg = self.get_average_throughput()

        # Calculate variance
        variance = sum((m.throughput_kbps - avg) ** 2 for m in self.history) / len(self.history)

        # Calculate standard deviation
        jitter = variance ** 0.5

        return jitter

    def get_last_throughput(self) -> Optional[float]:
        """
        Get the most recent throughput measurement.

        Returns:
            Most recent throughput in kbps, or None if history is empty
        """
        if not self.history:
            return None

        return self.history[-1].throughput_kbps

    def get_throughput_trend(self) -> str:
        """
        Determine if throughput is increasing, decreasing, or stable.

        Returns:
            "increasing", "decreasing", or "stable"

        Raises:
            RuntimeError: If history has less than 2 measurements
        """
        if len(self.history) < 2:
            raise RuntimeError("Need at least 2 measurements to calculate trend")

        # Get first half and second half
        mid = len(self.history) // 2
        first_half = list(self.history)[: len(self.history) - mid]
        second_half = list(self.history)[len(self.history) - mid :]

        first_avg = sum(m.throughput_kbps for m in first_half) / len(first_half)
        second_avg = sum(m.throughput_kbps for m in second_half) / len(second_half)

        # Allow 35% tolerance for stability (to account for natural timing variations)
        threshold = first_avg * 0.35

        if second_avg > first_avg + threshold:
            return "increasing"
        elif second_avg < first_avg - threshold:
            return "decreasing"
        else:
            return "stable"

    def clear_history(self) -> None:
        """Clear all measurements from history."""
        self.history.clear()

    def __repr__(self) -> str:
        """Return string representation."""
        if not self.history:
            return "ThroughputMeter(empty)"

        return (
            f"ThroughputMeter(measurements={len(self.history)}, "
            f"avg={self.get_average_throughput():.2f} kbps)"
        )
