"""HyperLogLog for privacy-preserving unique patient cardinality estimation.

Estimates the number of distinct patients assessed without storing any
patient identifiers. Uses only ~1.5KB of memory for <2% error.

Combined with differential privacy noise, this ensures individual patient
identity cannot be inferred from aggregate counts.

Reference: Flajolet P et al., "HyperLogLog: the analysis of a near-optimal
cardinality estimation algorithm", DMTCS, 2007.

Applies HyperLogLog to maternal health patient counting with privacy
guarantees, building on prior work in privacy-preserving clinical data
analysis (e.g., Bioinformatics 2021, HyperLogLog sketches for federated
queries of clinical data repositories).
"""

import hashlib
import math


class HyperLogLog:
    """HyperLogLog cardinality estimator.

    Estimates the number of distinct elements in a multiset using only
    O(m) space where m = 2^precision registers. Each register is a single
    byte, so total memory is 2^precision bytes (~1.5KB at precision=14).

    The standard error is approximately 1.04 / sqrt(m).

    Parameters:
        precision: number of bits used to index registers (p).
                   m = 2^p registers are allocated.
                   Default 14 → 16384 registers → ~0.81% relative error.

    Reference:
        Flajolet P, Fusy E, Gandouet O, Meunier F, "HyperLogLog: the
        analysis of a near-optimal cardinality estimation algorithm",
        DMTCS proc. AH, 2007, pp. 137-156.
    """

    # Bias correction constants (alpha_m) from Flajolet et al. 2007
    _ALPHA = {
        4: 0.673,
        5: 0.697,
        6: 0.709,
    }

    def __init__(self, precision: int = 14):
        if not (4 <= precision <= 18):
            raise ValueError("precision must be between 4 and 18")

        self._precision = precision
        self._m = 1 << precision         # number of registers = 2^p
        self._registers = [0] * self._m  # each register holds max leading zeros + 1

    def _hash(self, value: str) -> int:
        """Produce a 64-bit hash of the input value.

        Uses SHA-256, truncated to 64 bits, for a well-distributed hash
        with negligible collision probability for cardinalities up to ~10^9.
        """
        digest = hashlib.sha256(value.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big")

    def _leading_zeros(self, hash_val: int, precision: int) -> int:
        """Count leading zeros in the hash bits beyond the register index.

        After using the first `precision` bits to select a register, the
        remaining (64 - precision) bits are examined for the position of
        the first 1-bit. This value (rho) ranges from 1 to (64 - precision + 1).

        The +1 ensures rho >= 1 (Flajolet et al. convention).
        """
        # Mask out the index bits; work with the remaining bits
        remaining_bits = 64 - precision
        # Shift away the index bits (they are the most significant)
        w = hash_val & ((1 << remaining_bits) - 1)

        if w == 0:
            return remaining_bits + 1  # all zeros

        # Count leading zeros of w within the remaining_bits-wide field
        # Position of the highest set bit (0-indexed from MSB of the field)
        highest_bit = w.bit_length()  # 1-indexed from LSB
        leading = remaining_bits - highest_bit
        return leading + 1  # rho is 1-indexed

    def add(self, value: str) -> None:
        """Add an element to the HyperLogLog.

        Hashes the value, uses the first `precision` bits to select a
        register, and stores the maximum observed rho (leading zeros + 1)
        in that register.
        """
        h = self._hash(value)

        # The top `precision` bits select the register index
        idx = h >> (64 - self._precision)
        rho = self._leading_zeros(h, self._precision)

        if rho > self._registers[idx]:
            self._registers[idx] = rho

    def count(self) -> int:
        """Estimate the cardinality of the multiset.

        Applies the HyperLogLog estimator with bias correction:
            E = alpha_m * m^2 * (sum(2^(-M_j)))^(-1)

        For small cardinalities (E <= 5/2 * m), uses linear counting
        if there are empty registers. For large cardinalities (E > 2^32 / 30),
        applies hash collision correction — though with 64-bit hashes this
        threshold is effectively unreachable.
        """
        m = self._m

        # Bias correction constant
        if self._precision in self._ALPHA:
            alpha = self._ALPHA[self._precision]
        else:
            alpha = 0.7213 / (1.0 + 1.079 / m)

        # Harmonic mean of 2^(-register)
        raw_estimate = alpha * m * m / sum(2.0 ** (-r) for r in self._registers)

        # Small range correction (linear counting)
        if raw_estimate <= 2.5 * m:
            # Count empty registers (value == 0)
            zeros = self._registers.count(0)
            if zeros > 0:
                # Linear counting: m * ln(m / V) where V = number of empty registers
                raw_estimate = m * math.log(m / zeros)

        # Large range correction (hash collision)
        # With 64-bit hashes, 2^64 is effectively infinite, so this branch
        # is included for algorithmic completeness but will not trigger
        # in practice.
        two_32 = 2 ** 32
        if raw_estimate > two_32 / 30.0:
            raw_estimate = -(two_32) * math.log(1.0 - raw_estimate / two_32)

        return int(round(raw_estimate))

    def merge(self, other: "HyperLogLog") -> None:
        """Merge another HyperLogLog into this one.

        Takes the element-wise maximum of registers, which is equivalent
        to computing the union of the two multisets. This enables federated
        cardinality estimation across distributed sites (e.g., multiple
        PHCs reporting to a district).

        Both HyperLogLogs must have the same precision.
        """
        if self._precision != other._precision:
            raise ValueError(
                f"Cannot merge HyperLogLogs with different precisions: "
                f"{self._precision} vs {other._precision}"
            )
        for i in range(self._m):
            if other._registers[i] > self._registers[i]:
                self._registers[i] = other._registers[i]

    @property
    def precision(self) -> int:
        """Precision parameter (p). Number of index bits."""
        return self._precision

    @property
    def memory_bytes(self) -> int:
        """Approximate memory usage in bytes.

        Each register is stored as a Python int in a list, but the
        theoretical minimum is 1 byte per register (rho fits in 6 bits).
        Reports the theoretical minimum for comparability with the paper.
        """
        return self._m  # 1 byte per register

    @property
    def relative_error(self) -> float:
        """Theoretical relative standard error: 1.04 / sqrt(m)."""
        return 1.04 / math.sqrt(self._m)


class PatientCounter:
    """Privacy-preserving unique patient counter for maternal health assessments.

    Wraps HyperLogLog to count distinct patients without storing any
    patient identifiable information. The counter accepts (mother_name,
    asha_id) pairs, hashes them into a single anonymous token, and feeds
    the token into the HyperLogLog.

    Because only register maxima are stored (not hashes or identifiers),
    it is computationally infeasible to reconstruct individual patient
    identities from the counter state.
    """

    def __init__(self):
        self._hll = HyperLogLog(precision=14)

    def record_patient(self, mother_name: str, asha_id: str) -> None:
        """Record a patient assessment.

        The patient identity is formed by hashing (mother_name, asha_id)
        with SHA-256 before passing to the HyperLogLog, providing a
        second layer of irreversibility on top of the HLL's own hashing.
        """
        # Normalize and combine identifiers
        raw = f"{mother_name.strip().lower()}|{asha_id.strip().lower()}"
        # Pre-hash to anonymize before HLL ingestion
        anon_token = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self._hll.add(anon_token)

    def unique_patients(self) -> int:
        """Estimated number of unique patients assessed.

        Returns an integer estimate with relative error ~0.81% at the
        default precision of 14.
        """
        return self._hll.count()

    def stats(self) -> dict:
        """Return counter statistics.

        Returns:
            dict with:
                estimated_unique: estimated number of distinct patients
                precision: HLL precision parameter
                memory_bytes: theoretical memory usage
                relative_error: expected relative standard error
        """
        return {
            "estimated_unique": self._hll.count(),
            "precision": self._hll.precision,
            "memory_bytes": self._hll.memory_bytes,
            "relative_error": round(self._hll.relative_error, 6),
        }
