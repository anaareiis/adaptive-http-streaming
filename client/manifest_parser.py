"""Manifest parser for streaming protocols."""

import json
import requests
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin


class ManifestParser:
    """Parser for JSON manifest files from streaming server."""

    def __init__(self, manifest_url: str = None):
        """
        Initialize the manifest parser.

        Args:
            manifest_url: URL to the manifest file (e.g., 'http://server/manifest')
        """
        self.manifest_url = manifest_url
        self.manifest_data = None
        self.qualities = []
        self.servers = []
        self.segment_info = {}
        self.representations = None  # populated only with v2.0 format

    def download_manifest(self, manifest_url: Optional[str] = None) -> bool:
        """
        Download manifest from server.

        Args:
            manifest_url: URL to the manifest file. If not provided, uses the URL from __init__

        Returns:
            bool: True if successful, False otherwise

        Raises:
            ValueError: If no manifest URL is provided
            requests.RequestException: If download fails
        """
        url = manifest_url or self.manifest_url

        if not url:
            raise ValueError("Manifest URL not provided")

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Parse JSON
            self.manifest_data = response.json()
            self._parse_manifest()

            return True

        except requests.exceptions.ConnectionError as e:
            raise requests.RequestException(f"Server unavailable: {e}")
        except requests.exceptions.Timeout as e:
            raise requests.RequestException(f"Request timeout: {e}")
        except requests.exceptions.HTTPError as e:
            raise requests.RequestException(f"HTTP error: {e}")
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in manifest: {e}", "", 0)

    def load_from_dict(self, data: Dict) -> bool:
        """
        Load manifest from dictionary (useful for testing).

        Args:
            data: Dictionary containing manifest data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.manifest_data = data
            self._parse_manifest()
            return True
        except KeyError as e:
            raise KeyError(f"Missing key in manifest data: {e}")

    def _parse_manifest(self) -> None:
        """
        Parse manifest data into internal structures.

        Supports two formats:
        - Legacy format: 'qualities' list with name/bitrate, 'segment' dict with duration/total
        - v2.0 format: 'representations' list with quality/bitrate_kbps/url_path,
          'segment_duration_s' at root level

        Raises:
            KeyError: If required fields are missing
            ValueError: If data format is invalid
        """
        if not self.manifest_data:
            raise ValueError("No manifest data to parse")

        # Parse qualities — detect format by key presence
        if "representations" in self.manifest_data:
            reps = self.manifest_data["representations"]
            if not isinstance(reps, list):
                raise ValueError("'representations' must be a list")
            self.representations = reps
            # Map to the standard internal format expected by ABR classes
            self.qualities = [
                {"name": r["quality"], "bitrate": r["bitrate_kbps"]}
                for r in reps
            ]
        elif "qualities" in self.manifest_data:
            self.qualities = self.manifest_data["qualities"]
            if not isinstance(self.qualities, list):
                raise ValueError("'qualities' must be a list")
            self.representations = None
        else:
            raise KeyError("Missing 'qualities' or 'representations' field in manifest")

        # Parse servers
        if "servers" not in self.manifest_data:
            raise KeyError("Missing 'servers' field in manifest")

        self.servers = self.manifest_data["servers"]
        if not isinstance(self.servers, list):
            raise ValueError("'servers' must be a list")

        # Parse segment info — detect format
        if "segment_duration_s" in self.manifest_data:
            # v2.0: duration at root level, total segments may not exist
            self.segment_info = {
                "duration": float(self.manifest_data["segment_duration_s"]),
            }
            if "total_segments" in self.manifest_data:
                self.segment_info["total"] = int(self.manifest_data["total_segments"])
        elif "segment" in self.manifest_data:
            self.segment_info = self.manifest_data["segment"]
            if not isinstance(self.segment_info, dict):
                raise ValueError("'segment' must be a dictionary")
        else:
            raise KeyError("Missing 'segment' or 'segment_duration_s' field in manifest")

    def get_qualities(self) -> List[Dict]:
        """
        Get list of available qualities.

        Returns:
            List of quality dictionaries with 'name' and 'bitrate' fields

        Example:
            [
                {"name": "240p", "bitrate": 200},
                {"name": "360p", "bitrate": 400},
                {"name": "720p", "bitrate": 800}
            ]
        """
        if not self.manifest_data:
            raise RuntimeError("No manifest loaded. Call download_manifest() first.")

        return self.qualities

    def get_bitrate(self, quality: str) -> int:
        """
        Get bitrate for a specific quality.

        Args:
            quality: Quality name (e.g., '240p', '360p')

        Returns:
            Bitrate in kbps

        Raises:
            ValueError: If quality is not found
        """
        if not self.manifest_data:
            raise RuntimeError("No manifest loaded. Call download_manifest() first.")

        for q in self.qualities:
            if q.get("name") == quality:
                return q.get("bitrate")

        raise ValueError(f"Quality '{quality}' not found in manifest")

    def get_servers(self) -> List[Dict]:
        """
        Get list of available servers.

        Returns:
            List of server dictionaries with 'url' and 'priority' fields

        Example:
            [
                {"url": "http://server1.com", "priority": 1},
                {"url": "http://server2.com", "priority": 2}
            ]
        """
        if not self.manifest_data:
            raise RuntimeError("No manifest loaded. Call download_manifest() first.")

        # Sort by priority
        return sorted(self.servers, key=lambda s: s.get("priority", float("inf")))

    def get_segment_duration(self) -> float:
        """
        Get segment duration in seconds.

        Returns:
            Duration of each segment in seconds

        Raises:
            KeyError: If duration not found
        """
        if not self.manifest_data:
            raise RuntimeError("No manifest loaded. Call download_manifest() first.")

        if "duration" not in self.segment_info:
            raise KeyError("Missing 'duration' in segment info")

        return float(self.segment_info["duration"])

    def get_total_segments(self) -> Optional[int]:
        """
        Get total number of segments.

        Returns:
            Total number of segments, or None if not specified (v2.0 format)
        """
        if not self.manifest_data:
            raise RuntimeError("No manifest loaded. Call download_manifest() first.")

        if "total" in self.segment_info:
            return int(self.segment_info["total"])

        return None

    def get_representations(self) -> List[Dict]:
        """
        Get full list of representations (v2.0 format).

        Returns:
            List of representation dicts with quality, bitrate_kbps, segment_bytes, url_path

        Raises:
            RuntimeError: If manifest not loaded or format does not have representations
        """
        if not self.manifest_data:
            raise RuntimeError("No manifest loaded. Call download_manifest() first.")

        if self.representations is None:
            raise RuntimeError(
                "Manifest does not contain representations (legacy format). "
                "Use get_qualities() instead."
            )

        return self.representations.copy()

    def get_representation_url(self, quality: str) -> str:
        """
        Get the URL path for a specific quality level.

        For v2.0 manifests, returns the url_path field from representations.
        For legacy manifests, returns a fallback path '/segment/{quality}'.

        Args:
            quality: Quality name (e.g., '240p', '720p')

        Returns:
            URL path string (e.g., '/segment/240p')
        """
        if not self.manifest_data:
            raise RuntimeError("No manifest loaded. Call download_manifest() first.")

        if self.representations is not None:
            for rep in self.representations:
                if rep["quality"] == quality:
                    return rep["url_path"]
            raise ValueError(f"Quality '{quality}' not found in representations")

        # Fallback for legacy format
        return f"/segment/{quality}"

    def get_primary_server(self) -> str:
        """
        Get the primary (highest priority) server URL.

        Returns:
            URL of the primary server

        Raises:
            IndexError: If no servers available
        """
        servers = self.get_servers()
        if not servers:
            raise IndexError("No servers available")

        return servers[0]["url"]

    def __repr__(self) -> str:
        """Return string representation of manifest parser."""
        if not self.manifest_data:
            return "ManifestParser(not loaded)"

        return (
            f"ManifestParser(qualities={len(self.qualities)}, "
            f"servers={len(self.servers)}, "
            f"segment_duration={self.get_segment_duration()})"
        )
