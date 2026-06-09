"""Adaptive Bitrate (ABR) algorithm implementation."""

from typing import List, Dict, Optional
from datetime import datetime


class RateBasedABR:
    """Rate-based ABR algorithm for quality selection."""

    SAFETY_FACTOR = 0.85  # 15% safety margin
    DEFAULT_MIN_QUALITY = "240p"

    def __init__(self):
        """Initialize the rate-based ABR algorithm."""
        self.decision_history = []
        self.current_quality = None

    def select_quality(
        self, throughput_kbps: float, qualities: List[Dict]
    ) -> str:
        """
        Select quality based on observed throughput.

        Algorithm:
        1. Calculate safety limit: throughput * SAFETY_FACTOR
        2. Find the highest quality with bitrate <= limit
        3. If no quality fits, fallback to minimum quality (240p)

        Args:
            throughput_kbps: Measured throughput in kbps
            qualities: List of quality dicts with 'name' and 'bitrate' fields

        Returns:
            Selected quality name (e.g., '240p', '720p')

        Raises:
            ValueError: If qualities list is empty or invalid
            TypeError: If throughput_kbps is not numeric
        """
        if not isinstance(throughput_kbps, (int, float)):
            raise TypeError(f"throughput_kbps must be numeric, got {type(throughput_kbps)}")

        if not qualities or len(qualities) == 0:
            raise ValueError("Qualities list is empty")

        # Validate quality structure
        for q in qualities:
            if not isinstance(q, dict) or "name" not in q or "bitrate" not in q:
                raise ValueError(f"Invalid quality format: {q}")

        # Calculate safety limit
        safety_limit = throughput_kbps * self.SAFETY_FACTOR

        # Sort qualities by bitrate (ascending)
        sorted_qualities = sorted(qualities, key=lambda q: q["bitrate"])

        # Find the highest quality that fits within the limit
        selected_quality = None
        for quality in sorted_qualities:
            if quality["bitrate"] <= safety_limit:
                selected_quality = quality["name"]

        # Fallback to minimum quality if none fit
        if selected_quality is None:
            # Check if minimum quality exists
            min_qualities = [q for q in qualities if q["name"] == self.DEFAULT_MIN_QUALITY]
            if min_qualities:
                selected_quality = self.DEFAULT_MIN_QUALITY
            else:
                # If 240p doesn't exist, use the absolute minimum
                selected_quality = sorted_qualities[0]["name"]

        # Record decision
        self._record_decision(throughput_kbps, safety_limit, selected_quality)
        self.current_quality = selected_quality

        return selected_quality

    def _record_decision(
        self, throughput: float, limit: float, quality: str
    ) -> None:
        """
        Record a quality selection decision in history.

        Args:
            throughput: Measured throughput
            limit: Safety limit used
            quality: Selected quality
        """
        decision = {
            "timestamp": datetime.now(),
            "throughput_kbps": throughput,
            "safety_limit_kbps": limit,
            "selected_quality": quality,
        }
        self.decision_history.append(decision)

    def get_decision_history(self) -> List[Dict]:
        """
        Get the complete decision history.

        Returns:
            List of decision dictionaries
        """
        return self.decision_history.copy()

    def get_last_decision(self) -> Optional[Dict]:
        """
        Get the last quality selection decision.

        Returns:
            Last decision dict or None if no decisions made yet
        """
        if self.decision_history:
            return self.decision_history[-1].copy()
        return None

    def get_decision_count(self, quality: Optional[str] = None) -> int:
        """
        Get count of decisions for a specific quality or total.

        Args:
            quality: Quality name to filter by. If None, returns total count.

        Returns:
            Number of decisions matching criteria
        """
        if quality is None:
            return len(self.decision_history)

        return sum(
            1 for d in self.decision_history if d["selected_quality"] == quality
        )

    def get_quality_switches(self) -> List[Dict]:
        """
        Get list of all quality switches in history.

        Returns:
            List of switches with previous and new quality
        """
        if len(self.decision_history) < 2:
            return []

        switches = []
        for i in range(1, len(self.decision_history)):
            prev_quality = self.decision_history[i - 1]["selected_quality"]
            curr_quality = self.decision_history[i]["selected_quality"]

            if prev_quality != curr_quality:
                switches.append(
                    {
                        "from_quality": prev_quality,
                        "to_quality": curr_quality,
                        "timestamp": self.decision_history[i]["timestamp"],
                        "throughput_kbps": self.decision_history[i]["throughput_kbps"],
                    }
                )

        return switches

    def reset_history(self) -> None:
        """Clear all decision history."""
        self.decision_history = []
        self.current_quality = None

    def __repr__(self) -> str:
        """Return string representation of ABR instance."""
        return (
            f"RateBasedABR(current_quality={self.current_quality}, "
            f"decisions={len(self.decision_history)}, "
            f"safety_factor={self.SAFETY_FACTOR})"
        )


class BufferBasedABR:
    """Buffer-based ABR algorithm for quality selection."""

    # Thresholds de segurança em segundos para o estado do buffer
    LOW_BUFFER_THRESHOLD = 5.0    # Abaixo disso, força qualidade mínima para evitar stall
    MEDIUM_BUFFER_THRESHOLD = 15.0 # Buffer seguro para qualidades intermediárias
    HIGH_BUFFER_THRESHOLD = 30.0   # Buffer abundante, pode usar qualidade máxima

    def __init__(self):
        """Initialize the buffer-based ABR algorithm."""
        self.decision_history = []
        self.current_quality = None

    def select_quality(
        self, current_buffer_s: float, qualities: List[Dict]
    ) -> str:
        """
        Select quality based on the current buffer level in seconds.

        Algorithm:
        1. Sort available qualities by bitrate (lowest to highest).
        2. If buffer < 5s: fallback to lowest quality (240p).
        3. If buffer < 15s: select a conservative intermediate quality.
        4. If buffer < 30s: select a high intermediate quality.
        5. If buffer >= 30s: safely select the maximum available quality.
        """
        if not isinstance(current_buffer_s, (int, float)):
            raise TypeError(f"current_buffer_s must be numeric, got {type(current_buffer_s)}")
        if not qualities:
            raise ValueError("Qualities list cannot be empty")

        # 1. Ordena as qualidades do menor bitrate para o maior
        sorted_qualities = sorted(qualities, key=lambda x: x.get("bitrate", 0))
        
        # 2. Tomada de decisão por patamares de buffer (Seconds-based Thresholds)
        if current_buffer_s < self.LOW_BUFFER_THRESHOLD:
            selected = sorted_qualities[0]["name"]
        elif current_buffer_s < self.MEDIUM_BUFFER_THRESHOLD:
            idx = min(1, len(sorted_qualities) - 1)
            selected = sorted_qualities[idx]["name"]
        elif current_buffer_s < self.HIGH_BUFFER_THRESHOLD:
            idx = min(2, len(sorted_qualities) - 1)
            selected = sorted_qualities[idx]["name"]
        else:
            selected = sorted_qualities[-1]["name"]

        # 3. Registrar histórico (Mantendo a compatibilidade com a sua estrutura rica)
        self.current_quality = selected
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "buffer_level_s": current_buffer_s,
            "selected_quality": selected,
        })

        return selected

    # --- Seus métodos auxiliares perfeitamente mantidos ---
    def get_decision_history(self) -> List[Dict]:
        return self.decision_history

    def get_last_decision(self) -> Optional[Dict]:
        if self.decision_history:
            return self.decision_history[-1].copy()
        return None

    def get_decision_count(self, quality: Optional[str] = None) -> int:
        if quality is None:
            return len(self.decision_history)
        return sum(1 for d in self.decision_history if d["selected_quality"] == quality)

    def get_quality_switches(self) -> List[Dict]:
        if len(self.decision_history) < 2:
            return []
        switches = []
        for i in range(1, len(self.decision_history)):
            prev = self.decision_history[i - 1]["selected_quality"]
            curr = self.decision_history[i]["selected_quality"]
            if prev != curr:
                switches.append({
                    "from_quality": prev,
                    "to_quality": curr,
                    "timestamp": self.decision_history[i]["timestamp"],
                    "buffer_level_s": self.decision_history[i]["buffer_level_s"],
                })
        return switches

    def reset_history(self) -> None:
        self.decision_history = []
        self.current_quality = None

    def __repr__(self) -> str:
        return f"BufferBasedABR(current_quality='{self.current_quality}', decisions={len(self.decision_history)})"