"""Bloom filter for space-efficient duplicate assessment detection.

Prevents redundant maternal health risk assessments for the same patient
within a configurable time window. Operates in O(1) time with sub-linear
space.

Part of the probabilistic data structures framework for resource-constrained
healthcare systems, alongside Count-Min Sketch (blood bank inventory) and
HyperLogLog (unique patient counting).

Reference: Bloom B, "Space/time trade-offs in hash coding with allowable errors",
Communications of the ACM, 1970.
"""

import hashlib
import math
from datetime import datetime, timezone


class BloomFilter:
    """Space-efficient probabilistic set membership test.

    Supports O(1) insertion and O(1) membership queries with a tunable
    false positive rate and zero false negatives.

    Parameters:
        expected_items: anticipated number of distinct items (n)
        false_positive_rate: target false positive probability (p)

    The optimal bit-array size and hash count are derived from the
    classic Bloom filter formulas:
        m = -(n * ln(p)) / (ln(2)^2)
        k = (m / n) * ln(2)

    Reference: Bloom B, "Space/time trade-offs in hash coding with
    allowable errors", Commun. ACM 13(7), 1970, pp. 422-426.
    """

    def __init__(
        self,
        expected_items: int = 1000,
        false_positive_rate: float = 0.01,
    ):
        if expected_items <= 0:
            raise ValueError("expected_items must be positive")
        if not (0 < false_positive_rate < 1):
            raise ValueError("false_positive_rate must be in (0, 1)")

        self._expected_items = expected_items
        self._target_fp_rate = false_positive_rate

        # Optimal bit-array size: m = -(n * ln(p)) / (ln(2)^2)
        ln2_sq = math.log(2) ** 2
        self._size_bits = int(
            math.ceil(-(expected_items * math.log(false_positive_rate)) / ln2_sq)
        )
        # Ensure at least 1 bit
        self._size_bits = max(self._size_bits, 1)

        # Optimal number of hash functions: k = (m/n) * ln(2)
        self._num_hashes = int(
            math.ceil((self._size_bits / expected_items) * math.log(2))
        )
        self._num_hashes = max(self._num_hashes, 1)

        # Bit array stored as a mutable bytearray for compactness
        self._bits = bytearray((self._size_bits + 7) // 8)
        self._items_added = 0

    def _hashes(self, key: str) -> list[int]:
        """Generate k hash positions using double hashing.

        Uses MD5 and SHA-256 as the two base hash functions. The i-th
        hash position is computed as:
            h_i(key) = (h1 + i * h2) mod m

        This is the Kirsch-Mitzenmacker double hashing technique:
        Kirsch A, Mitzenmacker M, "Less Hashing, Same Performance:
        Building a Better Bloom Filter", Random Struct. Alg. 33(2), 2008.
        """
        # Base hash 1: MD5 → 128-bit → first 8 bytes as uint64
        md5_digest = hashlib.md5(key.encode("utf-8")).digest()
        h1 = int.from_bytes(md5_digest[:8], byteorder="big")

        # Base hash 2: SHA-256 → 256-bit → first 8 bytes as uint64
        sha_digest = hashlib.sha256(key.encode("utf-8")).digest()
        h2 = int.from_bytes(sha_digest[:8], byteorder="big")

        positions = []
        for i in range(self._num_hashes):
            pos = (h1 + i * h2) % self._size_bits
            positions.append(pos)
        return positions

    def _get_bit(self, pos: int) -> bool:
        """Read a single bit from the bit array."""
        byte_idx = pos >> 3  # pos // 8
        bit_idx = pos & 7    # pos % 8
        return bool(self._bits[byte_idx] & (1 << bit_idx))

    def _set_bit(self, pos: int) -> None:
        """Set a single bit in the bit array."""
        byte_idx = pos >> 3
        bit_idx = pos & 7
        self._bits[byte_idx] |= (1 << bit_idx)

    def add(self, key: str) -> bool:
        """Add a key to the filter.

        Returns:
            True if the key probably already existed (all k bits were
            already set — possible false positive).
            False if the key is definitely new (at least one bit was unset).
        """
        positions = self._hashes(key)
        probably_exists = all(self._get_bit(pos) for pos in positions)

        for pos in positions:
            self._set_bit(pos)

        self._items_added += 1
        return probably_exists

    def contains(self, key: str) -> bool:
        """Probabilistic membership test.

        Returns:
            True if the key is probably in the set (may be false positive).
            False if the key is definitely not in the set.
        """
        return all(self._get_bit(pos) for pos in self._hashes(key))

    def clear(self) -> None:
        """Reset the filter, clearing all bits and the item counter."""
        self._bits = bytearray((self._size_bits + 7) // 8)
        self._items_added = 0

    @property
    def size_bits(self) -> int:
        """Total size of the bit array in bits."""
        return self._size_bits

    @property
    def num_hashes(self) -> int:
        """Number of hash functions (k)."""
        return self._num_hashes

    @property
    def items_added(self) -> int:
        """Number of items added (including possible duplicates)."""
        return self._items_added

    @property
    def estimated_false_positive_rate(self) -> float:
        """Estimated current false positive rate based on items added.

        Formula: (1 - e^(-k*n/m))^k
        where k = num_hashes, n = items_added, m = size_bits.

        Reference: Bose P et al., "On the false-positive rate of Bloom
        filters", Inf. Process. Lett. 108(4), 2008, pp. 210-213.
        """
        if self._items_added == 0:
            return 0.0
        exponent = -(self._num_hashes * self._items_added) / self._size_bits
        return (1.0 - math.exp(exponent)) ** self._num_hashes


class AssessmentDeduplicator:
    """Duplicate maternal health assessment detector using Bloom filter.

    Prevents redundant assessments for the same (mother, ASHA worker) pair
    within a configurable time window. The key is formed from the mother's
    name, the ASHA worker's ID, and the current date, so the filter
    automatically resets semantically each day.

    Designed for ASHA workers in the field with limited connectivity:
    the Bloom filter provides a lightweight, offline-capable mechanism
    to catch accidental duplicate submissions.
    """

    def __init__(self, window_hours: int = 24):
        self._window_hours = window_hours
        # Size for ~500 assessments/day with 1% FP rate
        self._filter = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        self._assessments_today = 0
        self._duplicates_caught = 0
        self._current_date = self._today_str()

    @staticmethod
    def _today_str() -> str:
        """Current date as YYYY-MM-DD string (UTC)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _make_key(self, mother_name: str, asha_id: str) -> str:
        """Create a deterministic key from patient + worker + date.

        The key incorporates the date so that the same patient can be
        reassessed on a different day without triggering a duplicate warning.
        The raw names are hashed (SHA-256) to avoid storing PII in the key.
        """
        date_str = self._today_str()
        raw = f"{mother_name.strip().lower()}|{asha_id.strip().lower()}|{date_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _check_day_rollover(self) -> None:
        """If the date has changed, automatically reset the filter."""
        today = self._today_str()
        if today != self._current_date:
            self.reset_daily()
            self._current_date = today

    def check_duplicate(self, mother_name: str, asha_id: str) -> dict:
        """Check whether an assessment for this patient has already been recorded today.

        Returns:
            dict with:
                is_duplicate (bool): True if a matching assessment was found today
                should_proceed (bool): True — duplicates generate a warning but
                    the ASHA worker can override and proceed
                message (str): human-readable explanation
        """
        self._check_day_rollover()
        key = self._make_key(mother_name, asha_id)
        is_dup = self._filter.contains(key)

        if is_dup:
            self._duplicates_caught += 1
            return {
                "is_duplicate": True,
                "should_proceed": True,
                "message": (
                    f"An assessment for this patient by ASHA {asha_id} "
                    f"was already recorded today. You may proceed if a "
                    f"re-assessment is clinically necessary."
                ),
            }

        return {
            "is_duplicate": False,
            "should_proceed": True,
            "message": "No prior assessment found today. Proceed.",
        }

    def record_assessment(self, mother_name: str, asha_id: str) -> None:
        """Record that an assessment has been performed.

        Call this after the assessment is successfully submitted so that
        subsequent duplicate checks for the same patient + worker + date
        will return is_duplicate=True.
        """
        self._check_day_rollover()
        key = self._make_key(mother_name, asha_id)
        was_dup = self._filter.add(key)
        self._assessments_today += 1
        if was_dup:
            self._duplicates_caught += 1

    def reset_daily(self) -> None:
        """Clear the filter for a new day.

        Resets the Bloom filter, assessment count, and duplicate count.
        Called automatically on date rollover, or can be invoked manually.
        """
        self._filter.clear()
        self._assessments_today = 0
        self._duplicates_caught = 0
        self._current_date = self._today_str()

    def stats(self) -> dict:
        """Return operational statistics for the current day.

        Returns:
            dict with:
                assessments_today: total assessments recorded
                probable_duplicates_caught: number of duplicate detections
                filter_stats: Bloom filter parameters and current FP rate
        """
        self._check_day_rollover()
        return {
            "assessments_today": self._assessments_today,
            "probable_duplicates_caught": self._duplicates_caught,
            "filter_stats": {
                "size_bits": self._filter.size_bits,
                "num_hashes": self._filter.num_hashes,
                "items_added": self._filter.items_added,
                "estimated_false_positive_rate": round(
                    self._filter.estimated_false_positive_rate, 6
                ),
                "memory_bytes": (self._filter.size_bits + 7) // 8,
            },
        }
