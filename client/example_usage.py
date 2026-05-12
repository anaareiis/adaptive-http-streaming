"""Example usage of the ManifestParser."""

from manifest_parser import ManifestParser

# Example 1: Load manifest from server
print("=" * 60)
print("Example 1: Loading manifest from server")
print("=" * 60)

try:
    parser = ManifestParser(manifest_url="http://servidor/manifest")
    parser.download_manifest()
    print("✓ Manifest downloaded successfully")
except Exception as e:
    print(f"✗ Error: {e}")

# Example 2: Load manifest from dictionary (for testing)
print("\n" + "=" * 60)
print("Example 2: Loading manifest from dictionary")
print("=" * 60)

manifest_data = {
    "qualities": [
        {"name": "240p", "bitrate": 200},
        {"name": "360p", "bitrate": 400},
        {"name": "480p", "bitrate": 800},
        {"name": "720p", "bitrate": 1200},
        {"name": "1080p", "bitrate": 2500},
    ],
    "servers": [
        {"url": "http://server1.com/segments", "priority": 1},
        {"url": "http://server2.com/segments", "priority": 2},
        {"url": "http://server3.com/segments", "priority": 3},
    ],
    "segment": {"duration": 2.0, "total": 100},
}

parser = ManifestParser()
parser.load_from_dict(manifest_data)

print(f"Parser state: {parser}")

# Example 3: Query available qualities
print("\n" + "=" * 60)
print("Example 3: Query available qualities")
print("=" * 60)

qualities = parser.get_qualities()
print("Available qualities:")
for q in qualities:
    print(f"  - {q['name']}: {q['bitrate']} kbps")

# Example 4: Get bitrate for specific quality
print("\n" + "=" * 60)
print("Example 4: Get bitrate for specific quality")
print("=" * 60)

quality_name = "720p"
bitrate = parser.get_bitrate(quality_name)
print(f"Bitrate for {quality_name}: {bitrate} kbps")

# Example 5: Query available servers
print("\n" + "=" * 60)
print("Example 5: Query available servers")
print("=" * 60)

servers = parser.get_servers()
print("Available servers (sorted by priority):")
for server in servers:
    print(f"  - Priority {server['priority']}: {server['url']}")

# Example 6: Get primary server
print("\n" + "=" * 60)
print("Example 6: Get primary server")
print("=" * 60)

primary_server = parser.get_primary_server()
print(f"Primary server: {primary_server}")

# Example 7: Get segment information
print("\n" + "=" * 60)
print("Example 7: Get segment information")
print("=" * 60)

duration = parser.get_segment_duration()
total_segments = parser.get_total_segments()
total_duration = duration * total_segments

print(f"Segment duration: {duration} seconds")
print(f"Total segments: {total_segments}")
print(f"Total stream duration: {total_duration} seconds ({total_duration / 60:.1f} minutes)")

# Example 8: Error handling
print("\n" + "=" * 60)
print("Example 8: Error handling")
print("=" * 60)

try:
    invalid_bitrate = parser.get_bitrate("480i")
except ValueError as e:
    print(f"✓ Caught expected error: {e}")

try:
    empty_parser = ManifestParser()
    empty_parser.get_qualities()
except RuntimeError as e:
    print(f"✓ Caught expected error: {e}")
