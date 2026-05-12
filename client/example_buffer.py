"""Example usage of the BufferManager."""

from buffer_manager import BufferManager

print("=" * 70)
print("BufferManager Examples")
print("=" * 70)

# Example 1: Basic buffer operations
print("\nExample 1: Basic Buffer Operations")
print("-" * 70)

bm = BufferManager(max_buffer=60.0)
print(f"Initial state: {bm}")

# Download segments
print("\nDownloading segments:")
for i in range(3):
    bm.add_segment(4.0)
    print(f"  Segment {i+1}: buffer = {bm.current_buffer:.1f}s")

# Playback
print("\nPlayback (consuming buffer):")
times = [1.0, 1.5, 2.0, 2.5]
for elapsed in times:
    bm.consume(elapsed)
    print(f"  After {elapsed}s: buffer = {bm.current_buffer:.1f}s, can_play = {bm.can_play()}")

# Example 2: Playability check
print("\n" + "=" * 70)
print("Example 2: Playability Threshold")
print("=" * 70)

bm2 = BufferManager(max_buffer=30.0)
print(f"\nMinimum buffer to play: {bm2.MIN_BUFFER_TO_PLAY}s\n")

for buffer_level in [0.5, 1.5, 2.0, 2.5, 5.0]:
    bm2.current_buffer = buffer_level
    status = "✓ CAN PLAY" if bm2.can_play() else "✗ BUFFERING"
    print(f"  Buffer: {buffer_level}s → {status}")

# Example 3: Rebuffering detection
print("\n" + "=" * 70)
print("Example 3: Rebuffering Detection")
print("=" * 70)

bm3 = BufferManager(max_buffer=20.0)

print("\nScenario: Network stuttering\n")

events = [
    ("Download segment", lambda: bm3.add_segment(4.0)),
    ("Download segment", lambda: bm3.add_segment(4.0)),
    ("Playback 5s", lambda: bm3.consume(5.0)),
    ("Download segment", lambda: bm3.add_segment(4.0)),
    ("Playback 6s", lambda: bm3.consume(6.0)),  # Stutter - buffer exhausted
    ("Download segment", lambda: bm3.add_segment(4.0)),
    ("Playback 3s", lambda: bm3.consume(3.0)),
    ("Playback 3s", lambda: bm3.consume(3.0)),
    ("Playback 5s", lambda: bm3.consume(5.0)),  # Stutter again
]

for i, (action, func) in enumerate(events, 1):
    func()
    status = "📊"
    if bm3.get_rebuffer_count() > 0 and i == len(events):
        status = "🔴"
    print(f"{i:2}. {action:25s} → buffer: {bm3.current_buffer:5.1f}s "
          f"rebuffers: {bm3.get_rebuffer_count()} {status}")

print(f"\nRebuffering Statistics:")
print(f"  Total rebuffers: {bm3.get_rebuffer_count()}")
for event in bm3.get_rebuffer_history():
    print(f"    - Rebuffer #{event['rebuffer_number']} at {event['timestamp'].strftime('%H:%M:%S.%f')[:-3]}")

# Example 4: Buffer percentage monitoring
print("\n" + "=" * 70)
print("Example 4: Buffer Percentage Monitoring")
print("=" * 70)

bm4 = BufferManager(max_buffer=50.0)

print("\nBuffer filling up:\n")
for i in range(6):
    bm4.add_segment(10.0)
    percentage = bm4.get_buffer_percentage()
    bar_length = int(percentage / 5)
    bar = "█" * bar_length + "░" * (20 - bar_length)
    print(f"  [{bar}] {percentage:6.1f}% ({bm4.current_buffer:5.1f}s / {bm4.max_buffer}s)")

# Example 5: Complete streaming session
print("\n" + "=" * 70)
print("Example 5: Complete Streaming Session Simulation")
print("=" * 70)

bm5 = BufferManager(max_buffer=40.0)

# Simulate a 30-second stream with adaptive buffering
print("\nSimulating 30-second stream:\n")

segment_duration = 4.0  # 4 seconds per segment
current_time = 0
segment_num = 0
total_segments_needed = 8

while current_time < 30:
    # Download segments when buffer is below 50%
    if bm5.get_buffer_percentage() < 50 and segment_num < total_segments_needed:
        bm5.add_segment(segment_duration)
        segment_num += 1
        print(f"[{current_time:5.1f}s] Download segment {segment_num:2d} → "
              f"buffer: {bm5.current_buffer:5.1f}s ({bm5.get_buffer_percentage():5.1f}%)")

    # Playback
    playback_time = 1.0
    if bm5.can_play():
        bm5.consume(playback_time)
        current_time += playback_time

        # Show status every few seconds
        if int(current_time) % 5 == 0 or current_time >= 30:
            status = "▶️ PLAYING" if bm5.can_play() else "⏸️  BUFFERING"
            print(f"[{current_time:5.1f}s] {status:15s} buffer: {bm5.current_buffer:5.1f}s")
    else:
        print(f"[{current_time:5.1f}s] ⏸️  BUFFERING - waiting for segment")
        current_time += 0.1

print(f"\n📊 Final Statistics:")
stats = bm5.get_stats()
for key, value in stats.items():
    if isinstance(value, float):
        print(f"   {key:20s}: {value:8.2f}")
    else:
        print(f"   {key:20s}: {value}")

# Example 6: Danger zone warnings
print("\n" + "=" * 70)
print("Example 6: Buffer Warnings")
print("=" * 70)

bm6 = BufferManager(max_buffer=30.0)

# Fill buffer
bm6.add_segment(20.0)
print(f"\nInitial buffer: {bm6.current_buffer:.1f}s\n")

for second in range(0, 25, 1):
    bm6.consume(1.0)

    percentage = bm6.get_buffer_percentage()

    if percentage > 30:
        warning = "✓ Healthy"
    elif percentage > 10:
        warning = "⚠️  Warning - Low buffer"
    else:
        warning = "🔴 Critical - Rebuffering likely!"

    print(f"  {second+1:2d}s: {bm6.current_buffer:5.1f}s ({percentage:5.1f}%) {warning}")

print("\n" + "=" * 70)
