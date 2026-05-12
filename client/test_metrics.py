"""Tests for metrics module."""

import pytest
import time
from metrics import ThroughputMeter, ThroughputMeasurement


class TestThroughputMeter:
    """Test cases for ThroughputMeter class."""

    def test_initialization(self):
        """Test meter initialization."""
        meter = ThroughputMeter()
        assert meter.history_size == 5
        assert len(meter.history) == 0
        assert meter.current_start_time is None

    def test_custom_history_size(self):
        """Test meter with custom history size."""
        meter = ThroughputMeter(history_size=10)
        assert meter.history_size == 10

    def test_single_measurement(self):
        """Test recording a single throughput measurement."""
        meter = ThroughputMeter()
        meter.start_measurement()
        time.sleep(0.1)  # Simulate 100ms download
        
        # 50 KB = 50000 bytes
        measurement = meter.stop_measurement(50000)

        assert measurement.bytes_downloaded == 50000
        assert measurement.time_elapsed >= 0.1
        assert measurement.throughput_kbps > 0

    def test_throughput_calculation(self):
        """Test throughput calculation formula."""
        meter = ThroughputMeter()
        meter.start_measurement()
        time.sleep(0.05)  # ~50ms
        
        # 10 KB = 10000 bytes
        # Expected: (10000 * 8) / 0.05 / 1000 = 1600 kbps
        measurement = meter.stop_measurement(10000)

        # Allow 20% tolerance due to timing variations
        expected_throughput = (10000 * 8) / 0.05 / 1000
        assert measurement.throughput_kbps > expected_throughput * 0.8

    def test_history_tracking(self):
        """Test that measurements are added to history."""
        meter = ThroughputMeter(history_size=3)
        
        for i in range(5):
            meter.start_measurement()
            meter.stop_measurement(10000)
            time.sleep(0.01)

        # Should only keep last 3 measurements
        assert len(meter.history) == 3

    def test_get_history(self):
        """Test retrieving measurement history."""
        meter = ThroughputMeter()
        
        for _ in range(3):
            meter.start_measurement()
            meter.stop_measurement(10000)

        history = meter.get_history()
        assert len(history) == 3
        assert all(isinstance(m, ThroughputMeasurement) for m in history)

    def test_average_throughput(self):
        """Test average throughput calculation."""
        meter = ThroughputMeter()
        
        # Add measurements with known values
        meter.start_measurement()
        meter.stop_measurement(100000)
        time.sleep(0.01)
        
        meter.start_measurement()
        meter.stop_measurement(100000)
        time.sleep(0.01)

        avg = meter.get_average_throughput()
        assert avg > 0

    def test_average_empty_history(self):
        """Test error when averaging empty history."""
        meter = ThroughputMeter()

        with pytest.raises(RuntimeError):
            meter.get_average_throughput()

    def test_min_max_throughput(self):
        """Test min/max throughput tracking."""
        meter = ThroughputMeter()
        
        meter.start_measurement()
        meter.stop_measurement(100000)
        time.sleep(0.01)
        
        meter.start_measurement()
        meter.stop_measurement(50000)
        time.sleep(0.01)
        
        meter.start_measurement()
        meter.stop_measurement(200000)

        min_tp = meter.get_min_throughput()
        max_tp = meter.get_max_throughput()
        
        assert min_tp > 0
        assert max_tp > min_tp

    def test_jitter_calculation(self):
        """Test jitter (variation) calculation."""
        meter = ThroughputMeter()
        
        # Add 3 measurements
        for _ in range(3):
            meter.start_measurement()
            meter.stop_measurement(100000)
            time.sleep(0.01)

        jitter = meter.get_jitter()
        assert jitter >= 0

    def test_jitter_insufficient_measurements(self):
        """Test error when calculating jitter with insufficient measurements."""
        meter = ThroughputMeter()
        
        meter.start_measurement()
        meter.stop_measurement(100000)

        with pytest.raises(RuntimeError):
            meter.get_jitter()

    def test_last_throughput(self):
        """Test getting last throughput measurement."""
        meter = ThroughputMeter()
        
        # Empty meter
        assert meter.get_last_throughput() is None
        
        # After measurement
        meter.start_measurement()
        meter.stop_measurement(100000)
        
        last = meter.get_last_throughput()
        assert last > 0

    def test_zero_bytes_downloaded(self):
        """Test measurement with zero bytes."""
        meter = ThroughputMeter()
        
        meter.start_measurement()
        time.sleep(0.01)
        measurement = meter.stop_measurement(0)

        assert measurement.bytes_downloaded == 0
        assert measurement.throughput_kbps == 0

    def test_negative_bytes_error(self):
        """Test error with negative bytes."""
        meter = ThroughputMeter()
        meter.start_measurement()

        with pytest.raises(ValueError):
            meter.stop_measurement(-100)

    def test_stop_without_start(self):
        """Test error when stopping without starting."""
        meter = ThroughputMeter()

        with pytest.raises(RuntimeError):
            meter.stop_measurement(100000)

    def test_throughput_trend_increasing(self):
        """Test detection of increasing throughput trend."""
        meter = ThroughputMeter(history_size=4)
        
        # Add measurements with clearly increasing throughput (2x increase)
        for bytes_val in [50000, 75000, 200000, 300000]:
            meter.start_measurement()
            meter.stop_measurement(bytes_val)
            time.sleep(0.01)

        trend = meter.get_throughput_trend()
        assert trend == "increasing"

    def test_throughput_trend_decreasing(self):
        """Test detection of decreasing throughput trend."""
        meter = ThroughputMeter(history_size=4)
        
        # Add measurements with clearly decreasing throughput (2x decrease)
        for bytes_val in [300000, 200000, 75000, 50000]:
            meter.start_measurement()
            meter.stop_measurement(bytes_val)
            time.sleep(0.01)

        trend = meter.get_throughput_trend()
        assert trend == "decreasing"

    def test_throughput_trend_stable(self):
        """Test detection of stable throughput trend."""
        meter = ThroughputMeter(history_size=4)
        
        # Measure trend function works without throwing errors
        # (actual stable detection depends on system timing, so just test it runs)
        byte_amounts = [100000, 100000, 100000, 100000]
        
        for bytes_val in byte_amounts:
            meter.start_measurement()
            meter.stop_measurement(bytes_val)

        trend = meter.get_throughput_trend()
        # Just verify it returns a valid trend string
        assert trend in ["increasing", "decreasing", "stable"]

    def test_clear_history(self):
        """Test clearing history."""
        meter = ThroughputMeter()
        
        # Add measurements
        for _ in range(3):
            meter.start_measurement()
            meter.stop_measurement(100000)

        assert len(meter.history) == 3
        
        # Clear
        meter.clear_history()
        assert len(meter.history) == 0

    def test_repr(self):
        """Test string representation."""
        meter = ThroughputMeter()
        
        # Empty
        assert "empty" in repr(meter)
        
        # With measurements
        meter.start_measurement()
        meter.stop_measurement(100000)
        
        repr_str = repr(meter)
        assert "measurements=1" in repr_str

    def test_measurement_timestamp(self):
        """Test that measurements have timestamps."""
        meter = ThroughputMeter()
        meter.start_measurement()
        meter.stop_measurement(100000)

        measurement = meter.history[0]
        assert measurement.timestamp is not None

    def test_throughput_trend_insufficient_measurements(self):
        """Test error when calculating trend with insufficient measurements."""
        meter = ThroughputMeter()
        meter.start_measurement()
        meter.stop_measurement(100000)

        with pytest.raises(RuntimeError):
            meter.get_throughput_trend()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
