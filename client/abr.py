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
    """
    Buffer-Based ABR algorithm (Política 2).

    Selects quality based on buffer level rather than instantaneous throughput.
    This reduces oscillation in unstable networks because the buffer acts as
    a long-term indicator of network conditions.

    Zones:
        Reservoir [0, RESERVOIR): lowest quality — buffer critical, refill first
        Cushion [RESERVOIR, RESERVOIR+CUSHION): proportional to buffer fraction
        Full [RESERVOIR+CUSHION, ∞): highest quality — buffer comfortable

    Hysteresis:
        Downgrade: immediate (buffer drop is urgent)
        Upgrade: only after UPGRADE_HOLD consecutive segments above the threshold
    """

    RESERVOIR = 6.0    # seconds below which → minimum quality
    CUSHION = 40.0     # seconds of cushion zone above reservoir
    UPGRADE_HOLD = 3   # consecutive segments required to confirm an upgrade

    def __init__(self):
        """Initialize the buffer-based ABR algorithm."""
        self.decision_history: List[Dict] = []
        self.current_quality: Optional[str] = None
        self._pending_quality: Optional[str] = None
        self._pending_count: int = 0

    def select_quality(
        self, current_buffer_s: float, qualities: List[Dict]
    ) -> str:
        """
        Select quality based on the current buffer level in seconds.

        Args:
            current_buffer_s: Current buffer level in seconds
            qualities: List of dicts with 'name' and 'bitrate' fields

        Returns:
            Selected quality name

        Raises:
            TypeError: If current_buffer_s is not numeric
            ValueError: If qualities list is empty
        """
        if not isinstance(current_buffer_s, (int, float)):
            raise TypeError(f"current_buffer_s must be numeric, got {type(current_buffer_s)}")
        if not qualities:
            raise ValueError("Qualities list cannot be empty")

        sorted_qualities = sorted(qualities, key=lambda q: q.get("bitrate", 0))
        n = len(sorted_qualities)

        # Determine target quality from buffer zone
        if current_buffer_s < self.RESERVOIR:
            target = sorted_qualities[0]["name"]
        elif current_buffer_s >= self.RESERVOIR + self.CUSHION:
            target = sorted_qualities[-1]["name"]
        else:
            fraction = (current_buffer_s - self.RESERVOIR) / self.CUSHION
            index = min(int(fraction * n), n - 1)
            target = sorted_qualities[index]["name"]

        # Apply hysteresis
        if self.current_quality is None:
            self.current_quality = target
            self._pending_quality = None
            self._pending_count = 0
        else:
            rank = {q["name"]: i for i, q in enumerate(sorted_qualities)}
            current_rank = rank.get(self.current_quality, 0)
            target_rank = rank.get(target, 0)

            if target_rank < current_rank:
                # Downgrade: immediate
                self.current_quality = target
                self._pending_quality = None
                self._pending_count = 0
            elif target_rank > current_rank:
                # Upgrade: wait UPGRADE_HOLD confirmations
                if self._pending_quality == target:
                    self._pending_count += 1
                    if self._pending_count >= self.UPGRADE_HOLD:
                        self.current_quality = target
                        self._pending_quality = None
                        self._pending_count = 0
                else:
                    self._pending_quality = target
                    self._pending_count = 1
            else:
                # Same quality: reset pending upgrade
                self._pending_quality = None
                self._pending_count = 0

        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "buffer_level_s": current_buffer_s,
            "selected_quality": self.current_quality,
        })

        return self.current_quality

    def get_decision_history(self) -> List[Dict]:
        return self.decision_history.copy()

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
        self._pending_quality = None
        self._pending_count = 0

    def __repr__(self) -> str:
        return (
            f"BufferBasedABR(current_quality='{self.current_quality}', "
            f"decisions={len(self.decision_history)}, "
            f"reservoir={self.RESERVOIR}s, cushion={self.CUSHION}s)"
        )


class HybridABR:
    """
    Hybrid ABR algorithm (Política 3).

    Combines three signals instead of relying on a single one:

    1. EWMA of throughput — recent samples weigh more than older ones, the
       same idea TCP uses to estimate RTT (Jacobson/Karels): it smooths out
       noisy instantaneous measurements without losing the ability to react
       to a real trend, unlike RateBasedABR which reacts to every sample.

    2. Jitter penalty — derates the EWMA throughput proportionally to the
       measured jitter (jitter_ewma_ms), the same logic behind TCP's RTO
       calculation (RTO = RTT + 4*RTTVAR): the less predictable the delivery
       timing, the larger the safety margin subtracted from the estimate.
       This is the explicit treatment of high-jitter scenarios required by
       Tarefa 3 — a noisy connection gets a more conservative quality even
       if its average throughput looks fine.

    3. Buffer safety net — if the buffer drops below RESERVOIR (same
       threshold used by BufferBasedABR), the minimum quality is forced
       regardless of the throughput estimate, so an optimistic estimate
       can never cause a rebuffer.

    select_quality(throughput_kbps, jitter_ms, buffer_level_s, qualities)
    """

    EWMA_ALPHA = 0.3         # weight given to the most recent throughput sample
    JITTER_PENALTY_K = 2.0   # multiplier applied to the jitter ratio
    MAX_PENALTY = 0.9        # caps the penalty so throughput is never zeroed out
    SAFETY_FACTOR = 0.85     # same safety margin used by RateBasedABR
    RESERVOIR = 6.0          # same critical-buffer threshold used by BufferBasedABR

    def __init__(self):
        """Initialize the hybrid ABR algorithm."""
        self.ewma_throughput: Optional[float] = None
        self.decision_history: List[Dict] = []
        self.current_quality: Optional[str] = None

    def select_quality(
        self,
        throughput_kbps: float,
        jitter_ms: float,
        buffer_level_s: float,
        qualities: List[Dict],
    ) -> str:
        """
        Select quality combining EWMA throughput, a jitter penalty and a
        buffer safety net.

        Args:
            throughput_kbps: Throughput measured for the last segment
            jitter_ms: Jitter measured for the last segment (e.g. jitter_ewma_ms)
            buffer_level_s: Current buffer level in seconds
            qualities: List of dicts with 'name' and 'bitrate' fields

        Returns:
            Selected quality name

        Raises:
            ValueError: If qualities list is empty
        """
        if not qualities:
            raise ValueError("Qualities list is empty")

        # 1. EWMA of throughput
        if self.ewma_throughput is None:
            self.ewma_throughput = throughput_kbps
        else:
            self.ewma_throughput = (
                self.EWMA_ALPHA * throughput_kbps
                + (1 - self.EWMA_ALPHA) * self.ewma_throughput
            )

        # 2. Jitter penalty — derates the throughput estimate when delivery
        # timing is unstable.
        jitter_ratio = max(0.0, jitter_ms) / 1000.0
        penalty = min(self.MAX_PENALTY, self.JITTER_PENALTY_K * jitter_ratio)
        effective_throughput = self.ewma_throughput * (1 - penalty)

        # 3. Quality selection over the derated estimate, with the usual
        # safety margin.
        safety_limit = effective_throughput * self.SAFETY_FACTOR
        sorted_qualities = sorted(qualities, key=lambda q: q["bitrate"])
        selected = sorted_qualities[0]["name"]
        for quality in sorted_qualities:
            if quality["bitrate"] <= safety_limit:
                selected = quality["name"]

        # 4. Buffer safety net — never risk a rebuffer on an optimistic estimate.
        if buffer_level_s < self.RESERVOIR:
            selected = sorted_qualities[0]["name"]

        self.current_quality = selected
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "throughput_kbps": throughput_kbps,
            "ewma_throughput_kbps": round(self.ewma_throughput, 2),
            "jitter_ms": jitter_ms,
            "penalty": round(penalty, 4),
            "effective_throughput_kbps": round(effective_throughput, 2),
            "buffer_level_s": buffer_level_s,
            "selected_quality": selected,
        })

        return selected

    def get_decision_history(self) -> List[Dict]:
        return self.decision_history.copy()

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
        self.ewma_throughput = None

    def __repr__(self) -> str:
        return (
            f"HybridABR(current_quality='{self.current_quality}', "
            f"decisions={len(self.decision_history)}, "
            f"ewma_throughput={self.ewma_throughput})"
        )