"""Example usage of the Rate-Based ABR algorithm."""

from abr import RateBasedABR

# Sample qualities available
QUALITIES = [
    {"name": "240p", "bitrate": 200},
    {"name": "360p", "bitrate": 400},
    {"name": "480p", "bitrate": 800},
    {"name": "720p", "bitrate": 1200},
    {"name": "1080p", "bitrate": 2500},
]

print("=" * 60)
print("Rate-Based ABR Algorithm Examples")
print("=" * 60)

# Example 1: Basic quality selection
print("\nExample 1: Basic Quality Selection")
print("-" * 60)

abr = RateBasedABR()

# Simulate throughput measurements over time
throughputs = [250, 500, 1400, 3000, 800, 300, 1200]

print(f"Safety factor: {abr.SAFETY_FACTOR * 100}% (15% margin)\n")

for i, throughput in enumerate(throughputs, 1):
    quality = abr.select_quality(throughput, QUALITIES)
    safety_limit = throughput * abr.SAFETY_FACTOR
    print(f"Step {i}: Throughput={throughput:4.0f} kbps, "
          f"Limit={safety_limit:7.1f} kbps → Select: {quality:5s}")

# Example 2: Decision history
print("\n" + "=" * 60)
print("Example 2: Decision History")
print("=" * 60)

history = abr.get_decision_history()
print(f"\nTotal decisions: {len(history)}")
for i, decision in enumerate(history, 1):
    print(f"\n{i}. Quality: {decision['selected_quality']}")
    print(f"   Throughput: {decision['throughput_kbps']} kbps")
    print(f"   Safety Limit: {decision['safety_limit_kbps']:.1f} kbps")
    print(f"   Time: {decision['timestamp'].strftime('%H:%M:%S.%f')[:-3]}")

# Example 3: Quality switches
print("\n" + "=" * 60)
print("Example 3: Quality Switches")
print("=" * 60)

switches = abr.get_quality_switches()
print(f"\nTotal switches: {len(switches)}\n")

for i, switch in enumerate(switches, 1):
    print(f"{i}. {switch['from_quality']} → {switch['to_quality']}")
    print(f"   Throughput: {switch['throughput_kbps']} kbps")

# Example 4: Decision statistics
print("\n" + "=" * 60)
print("Example 4: Decision Statistics")
print("=" * 60)

print(f"\nTotal decisions: {abr.get_decision_count()}")
print(f"Total switches: {len(switches)}")
print("\nDecisions per quality:")

quality_names = sorted(set(q["name"] for q in QUALITIES))
for quality in quality_names:
    count = abr.get_decision_count(quality)
    if count > 0:
        print(f"  {quality}: {count} times")

# Example 5: Simulating streaming session
print("\n" + "=" * 60)
print("Example 5: Streaming Session Simulation")
print("=" * 60)

abr2 = RateBasedABR()

# Simulate a 10-second streaming with measurements every 2 seconds
# Throughput varies over time (e.g., network congestion)
session_throughputs = [
    800,    # Initial: good connection → 480p
    1200,   # Slight improvement → 720p
    1500,   # Better → still 720p
    600,    # Congestion → 360p
    400,    # More congestion → 240p
    700,    # Recovery → 360p
]

print("\nStreamlit throughput variation:\n")

total_bitrate_watched = 0
quality_times = {q["name"]: 0 for q in QUALITIES}

for t in session_throughputs:
    selected = abr2.select_quality(t, QUALITIES)
    # Find bitrate of selected quality
    bitrate = next(q["bitrate"] for q in QUALITIES if q["name"] == selected)
    total_bitrate_watched += bitrate
    quality_times[selected] += 1

print(f"Session throughput samples: {session_throughputs}")
print(f"\nQuality selections:")

for decision in abr2.get_decision_history():
    print(f"  {decision['selected_quality']} "
          f"(throughput: {decision['throughput_kbps']} kbps)")

print(f"\nStatistics:")
print(f"  Total measurements: {abr2.get_decision_count()}")
print(f"  Quality switches: {len(abr2.get_quality_switches())}")
print(f"  Most selected quality: {max(quality_times, key=quality_times.get)}")

# Example 6: Current state
print("\n" + "=" * 60)
print("Example 6: Current State")
print("=" * 60)

print(f"\nABR State: {abr2}")
print(f"Current quality: {abr2.current_quality}")
print(f"Last decision: {abr2.get_last_decision()}")

print("\n" + "=" * 60)
