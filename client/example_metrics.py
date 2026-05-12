"""Example usage of the ThroughputMeter."""

import time
from metrics import ThroughputMeter


def simulate_download(meter, bytes_size, delay=0.05):
    """Simulate a download and measure throughput."""
    meter.start_measurement()
    time.sleep(delay)  # Simulate network delay
    measurement = meter.stop_measurement(bytes_size)
    return measurement


print("=" * 70)
print("Example 1: Single Measurement")
print("=" * 70)

meter = ThroughputMeter()
print("\nSimulating a 100 KB download over 50ms...")
measurement = simulate_download(meter, 100000, delay=0.05)

print(f"Bytes downloaded: {measurement.bytes_downloaded} bytes")
print(f"Time elapsed: {measurement.time_elapsed:.3f} seconds")
print(f"Throughput: {measurement.throughput_kbps:.2f} kbps")

print("\n" + "=" * 70)
print("Example 2: Multiple Measurements with History")
print("=" * 70)

meter = ThroughputMeter(history_size=5)

print("\nSimulating 6 segment downloads...")
sizes = [100000, 120000, 90000, 110000, 130000, 95000]

for i, size in enumerate(sizes, 1):
    measurement = simulate_download(meter, size, delay=0.05)
    print(f"  Segment {i}: {measurement.throughput_kbps:.2f} kbps ({size} bytes)")

print("\n" + "=" * 70)
print("Example 3: Statistical Analysis")
print("=" * 70)

print(f"\nTotal measurements in history: {len(meter.get_history())}")
print(f"Average throughput: {meter.get_average_throughput():.2f} kbps")
print(f"Min throughput: {meter.get_min_throughput():.2f} kbps")
print(f"Max throughput: {meter.get_max_throughput():.2f} kbps")
print(f"Jitter (std deviation): {meter.get_jitter():.2f} kbps")
print(f"Last throughput: {meter.get_last_throughput():.2f} kbps")
print(f"Throughput trend: {meter.get_throughput_trend()}")

print("\n" + "=" * 70)
print("Example 4: Increasing Throughput Scenario")
print("=" * 70)

meter_increasing = ThroughputMeter(history_size=4)
print("\nSimulating improving network conditions...")

# Increasing throughput: larger files, same delay = higher kbps
sizes_increasing = [50000, 75000, 150000, 250000]
for i, size in enumerate(sizes_increasing, 1):
    measurement = simulate_download(meter_increasing, size, delay=0.05)
    print(f"  Segment {i}: {measurement.throughput_kbps:.2f} kbps")

trend = meter_increasing.get_throughput_trend()
print(f"\nDetected trend: {trend}")
assert trend == "increasing", "Should detect increasing trend"
print("✓ Correctly identified as INCREASING")

print("\n" + "=" * 70)
print("Example 5: Decreasing Throughput Scenario")
print("=" * 70)

meter_decreasing = ThroughputMeter(history_size=4)
print("\nSimulating degrading network conditions...")

# Decreasing throughput: smaller files, same delay = lower kbps
sizes_decreasing = [250000, 150000, 75000, 50000]
for i, size in enumerate(sizes_decreasing, 1):
    measurement = simulate_download(meter_decreasing, size, delay=0.05)
    print(f"  Segment {i}: {measurement.throughput_kbps:.2f} kbps")

trend = meter_decreasing.get_throughput_trend()
print(f"\nDetected trend: {trend}")
assert trend == "decreasing", "Should detect decreasing trend"
print("✓ Correctly identified as DECREASING")

print("\n" + "=" * 70)
print("Example 6: Error Handling")
print("=" * 70)

try:
    bad_meter = ThroughputMeter()
    bad_meter.stop_measurement(100000)
except RuntimeError as e:
    print(f"✓ Caught expected error: {e}")

try:
    bad_meter = ThroughputMeter()
    bad_meter.start_measurement()
    bad_meter.stop_measurement(-100)
except ValueError as e:
    print(f"✓ Caught expected error: {e}")

try:
    empty_meter = ThroughputMeter()
    empty_meter.get_average_throughput()
except RuntimeError as e:
    print(f"✓ Caught expected error: {e}")

print("\n" + "=" * 70)
print("All examples completed successfully!")
print("=" * 70)
