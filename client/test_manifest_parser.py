"""Tests for the manifest parser."""

import pytest
from manifest_parser import ManifestParser


# Sample manifest data for testing
SAMPLE_MANIFEST = {
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


class TestManifestParser:
    """Test cases for ManifestParser class."""

    def test_load_from_dict(self):
        """Test loading manifest from dictionary."""
        parser = ManifestParser()
        result = parser.load_from_dict(SAMPLE_MANIFEST)

        assert result is True
        assert parser.manifest_data is not None

    def test_get_qualities(self):
        """Test retrieving list of qualities."""
        parser = ManifestParser()
        parser.load_from_dict(SAMPLE_MANIFEST)

        qualities = parser.get_qualities()

        assert len(qualities) == 5
        assert qualities[0]["name"] == "240p"
        assert qualities[0]["bitrate"] == 200
        assert qualities[-1]["name"] == "1080p"
        assert qualities[-1]["bitrate"] == 2500

    def test_get_bitrate(self):
        """Test retrieving bitrate for specific quality."""
        parser = ManifestParser()
        parser.load_from_dict(SAMPLE_MANIFEST)

        assert parser.get_bitrate("240p") == 200
        assert parser.get_bitrate("720p") == 1200
        assert parser.get_bitrate("1080p") == 2500

    def test_get_bitrate_invalid_quality(self):
        """Test error when requesting invalid quality."""
        parser = ManifestParser()
        parser.load_from_dict(SAMPLE_MANIFEST)

        with pytest.raises(ValueError):
            parser.get_bitrate("480i")

    def test_get_servers(self):
        """Test retrieving list of servers sorted by priority."""
        parser = ManifestParser()
        parser.load_from_dict(SAMPLE_MANIFEST)

        servers = parser.get_servers()

        assert len(servers) == 3
        assert servers[0]["priority"] == 1
        assert servers[1]["priority"] == 2
        assert servers[2]["priority"] == 3

    def test_get_primary_server(self):
        """Test retrieving primary server."""
        parser = ManifestParser()
        parser.load_from_dict(SAMPLE_MANIFEST)

        primary = parser.get_primary_server()

        assert primary == "http://server1.com/segments"

    def test_get_segment_duration(self):
        """Test retrieving segment duration."""
        parser = ManifestParser()
        parser.load_from_dict(SAMPLE_MANIFEST)

        duration = parser.get_segment_duration()

        assert duration == 2.0
        assert isinstance(duration, float)

    def test_get_total_segments(self):
        """Test retrieving total number of segments."""
        parser = ManifestParser()
        parser.load_from_dict(SAMPLE_MANIFEST)

        total = parser.get_total_segments()

        assert total == 100

    def test_missing_qualities_field(self):
        """Test error when 'qualities' field is missing."""
        parser = ManifestParser()
        invalid_manifest = {
            "servers": [],
            "segment": {"duration": 2.0, "total": 100},
        }

        with pytest.raises(KeyError):
            parser.load_from_dict(invalid_manifest)

    def test_missing_servers_field(self):
        """Test error when 'servers' field is missing."""
        parser = ManifestParser()
        invalid_manifest = {
            "qualities": [],
            "segment": {"duration": 2.0, "total": 100},
        }

        with pytest.raises(KeyError):
            parser.load_from_dict(invalid_manifest)

    def test_missing_segment_field(self):
        """Test error when 'segment' field is missing."""
        parser = ManifestParser()
        invalid_manifest = {
            "qualities": [],
            "servers": [],
        }

        with pytest.raises(KeyError):
            parser.load_from_dict(invalid_manifest)

    def test_query_without_loading(self):
        """Test error when querying without loading manifest."""
        parser = ManifestParser()

        with pytest.raises(RuntimeError):
            parser.get_qualities()

        with pytest.raises(RuntimeError):
            parser.get_servers()

    def test_repr(self):
        """Test string representation of parser."""
        parser = ManifestParser()

        # Before loading
        assert "not loaded" in repr(parser)

        # After loading
        parser.load_from_dict(SAMPLE_MANIFEST)
        repr_str = repr(parser)

        assert "qualities=5" in repr_str
        assert "servers=3" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
