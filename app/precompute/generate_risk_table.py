"""Precompute the full Beta-Binomial posterior risk table for all 70,000 factor combinations.

Usage:
    python -m app.precompute.generate_risk_table

Generates data/risk_table.json with 5 x 4 x 5 x 5 x 7 x 4 x 5 = 70,000 entries,
each keyed by a 16-char SHA-256 hash of the discretized index tuple.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

from app.engines.risk_scoring import RiskScoringEngine


def main() -> None:
    engine = RiskScoringEngine()

    # Dimension sizes (must match RiskScoringEngine bucket definitions)
    n_age = len(engine.AGE_BUCKETS)        # 5
    n_parity = len(engine.PARITY_BUCKETS)  # 4
    n_hb = len(engine.HB_BUCKETS)          # 5
    n_bp = len(engine.BP_BUCKETS)          # 5
    n_gest = len(engine.GEST_BUCKETS)      # 7
    n_bmi = len(engine.BMI_BUCKETS)        # 4
    n_comp = len(engine.COMP_BUCKETS)      # 5

    total = n_age * n_parity * n_hb * n_bp * n_gest * n_bmi * n_comp
    print(f"Generating {total:,} risk table entries...")
    print(f"  Dimensions: age={n_age} x parity={n_parity} x hb={n_hb} x bp={n_bp} "
          f"x gest={n_gest} x bmi={n_bmi} x comp={n_comp}")

    table: dict[str, dict] = {}
    level_counts: Counter = Counter()
    count = 0
    t0 = time.time()

    for age_idx in range(n_age):
        for parity_idx in range(n_parity):
            for hb_idx in range(n_hb):
                for bp_idx in range(n_bp):
                    for gest_idx in range(n_gest):
                        for bmi_idx in range(n_bmi):
                            for comp_idx in range(n_comp):
                                key = RiskScoringEngine._compute_hash(
                                    age_idx, parity_idx, hb_idx, bp_idx,
                                    gest_idx, bmi_idx, comp_idx,
                                )
                                entry = engine._compute_risk(
                                    age_idx, parity_idx, hb_idx, bp_idx,
                                    gest_idx, bmi_idx, comp_idx,
                                )
                                table[key] = entry
                                level_counts[entry["risk_level"]] += 1
                                count += 1

                                if count % 10_000 == 0:
                                    elapsed = time.time() - t0
                                    print(f"  [{count:>6,} / {total:,}] "
                                          f"{count / total * 100:5.1f}%  "
                                          f"({elapsed:.1f}s elapsed)")

    elapsed = time.time() - t0
    print(f"\nGeneration complete in {elapsed:.1f}s")
    print(f"  Total entries: {len(table):,}")

    # Verify no hash collisions
    if len(table) != total:
        print(f"  WARNING: Expected {total:,} entries but got {len(table):,} "
              f"({total - len(table)} hash collisions!)", file=sys.stderr)

    # Risk level distribution
    print("\n  Risk level distribution:")
    for level in ["low", "medium", "high", "critical"]:
        n = level_counts[level]
        pct = n / total * 100
        print(f"    {level:>8s}: {n:>6,}  ({pct:5.1f}%)")

    # Score range
    scores = [entry["risk_score"] for entry in table.values()]
    print(f"\n  Score range: [{min(scores):.4f}, {max(scores):.4f}]")
    print(f"  Mean score:  {sum(scores) / len(scores):.4f}")

    # Write to disk
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "risk_table.json"

    print(f"\nWriting to {out_path} ...")
    with open(out_path, "w") as f:
        json.dump(table, f, separators=(",", ":"))

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  File size: {size_mb:.1f} MB")
    print("Done.")


if __name__ == "__main__":
    main()
