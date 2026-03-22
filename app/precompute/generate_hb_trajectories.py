"""Generate precomputed hemoglobin trajectory array and learned index.

Produces a sorted array of trajectory profiles covering all discretized
feature combinations, plus an O(1) lookup index mapping feature keys
to positions in the sorted array.

Usage:
    python -m app.precompute.generate_hb_trajectories
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

# Ensure the project root is on sys.path so the engine module can be imported
# when running as `python -m app.precompute.generate_hb_trajectories`
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.engines.anemia_prediction import AnemiaPredictionEngine


# Feature grid definitions
HB_LEVELS = [3.0 + i * 1.0 for i in range(17)]          # 3.0 .. 19.0  (17 levels)
GEST_WEEKS = [i * 4 for i in range(11)]                   # 0, 4, 8 .. 40 (11 levels)
IFA_COMPLIANCE = [0.0, 0.25, 0.5, 0.75, 1.0]             # 5 levels
DIETARY_SCORES = [0.0, 0.33, 0.67, 1.0]                   # 4 levels
PREV_ANEMIA = [False, True]                                # 2 levels

EXPECTED_TOTAL = len(HB_LEVELS) * len(GEST_WEEKS) * len(IFA_COMPLIANCE) * len(DIETARY_SCORES) * len(PREV_ANEMIA)

OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "hb_trajectories.json")


def generate() -> None:
    engine = AnemiaPredictionEngine()

    print(f"Generating hemoglobin trajectory profiles...")
    print(f"  Hb levels:       {len(HB_LEVELS)}  ({HB_LEVELS[0]:.1f} - {HB_LEVELS[-1]:.1f} g/dL)")
    print(f"  Gest weeks:      {len(GEST_WEEKS)}  ({GEST_WEEKS[0]} - {GEST_WEEKS[-1]})")
    print(f"  IFA compliance:  {len(IFA_COMPLIANCE)}")
    print(f"  Dietary scores:  {len(DIETARY_SCORES)}")
    print(f"  Prev anemia:     {len(PREV_ANEMIA)}")
    print(f"  Expected total:  {EXPECTED_TOTAL}")
    print()

    # Step 1: Compute all trajectory profiles keyed by discretized feature string
    keyed_trajectories: list[tuple[str, dict]] = []

    for hb in HB_LEVELS:
        for gw in GEST_WEEKS:
            for ifa in IFA_COMPLIANCE:
                for diet in DIETARY_SCORES:
                    for anemia in PREV_ANEMIA:
                        key = engine._discretize_features(hb, gw, ifa, diet, anemia)
                        result = engine._compute_trajectory(hb, gw, ifa, diet, anemia)
                        # Store trajectory profile (without current_hb which is input-specific)
                        profile = {
                            "predicted_delivery_hb": result["predicted_delivery_hb"],
                            "trajectory": result["trajectory"],
                            "risk_level": result["risk_level"],
                            "intervention_urgency": result["intervention_urgency"],
                            "compliance_impact": result["compliance_impact"],
                        }
                        keyed_trajectories.append((key, profile))

    assert len(keyed_trajectories) == EXPECTED_TOTAL, (
        f"Generated {len(keyed_trajectories)} trajectories, expected {EXPECTED_TOTAL}"
    )

    # Step 2: Sort trajectories by predicted_delivery_hb (ascending) for the learned index
    keyed_trajectories.sort(key=lambda kp: kp[1]["predicted_delivery_hb"])

    # Step 3: Build sorted trajectory array and index
    trajectories = []
    index: dict[str, int] = {}

    for pos, (key, profile) in enumerate(keyed_trajectories):
        trajectories.append(profile)
        index[key] = pos

    # Step 4: Compute statistics
    risk_counter: Counter = Counter()
    urgency_counter: Counter = Counter()
    delivery_hbs = []

    for profile in trajectories:
        risk_counter[profile["risk_level"]] += 1
        urgency_counter[profile["intervention_urgency"]] += 1
        delivery_hbs.append(profile["predicted_delivery_hb"])

    min_hb = min(delivery_hbs)
    max_hb = max(delivery_hbs)
    mean_hb = sum(delivery_hbs) / len(delivery_hbs)
    sorted_hbs = sorted(delivery_hbs)
    median_hb = sorted_hbs[len(sorted_hbs) // 2]

    # Step 5: Write output
    output = {
        "trajectories": trajectories,
        "index": index,
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_trajectories": len(trajectories),
            "feature_grid": {
                "hb_levels": len(HB_LEVELS),
                "gest_weeks": len(GEST_WEEKS),
                "ifa_compliance": len(IFA_COMPLIANCE),
                "dietary_scores": len(DIETARY_SCORES),
                "prev_anemia": len(PREV_ANEMIA),
            },
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    file_size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)

    # Step 6: Print statistics
    print(f"Generated {len(trajectories)} trajectory profiles")
    print(f"Saved to {OUTPUT_PATH} ({file_size_mb:.1f} MB)")
    print()
    print("Predicted delivery Hb distribution:")
    print(f"  Min:    {min_hb:.1f} g/dL")
    print(f"  Max:    {max_hb:.1f} g/dL")
    print(f"  Mean:   {mean_hb:.1f} g/dL")
    print(f"  Median: {median_hb:.1f} g/dL")
    print()
    print("Risk level distribution:")
    for level in ["critical", "high", "medium", "low"]:
        count = risk_counter.get(level, 0)
        pct = 100.0 * count / len(trajectories)
        print(f"  {level:10s}: {count:5d} ({pct:5.1f}%)")
    print()
    print("Intervention urgency distribution:")
    for urgency in ["emergency", "urgent", "soon", "routine"]:
        count = urgency_counter.get(urgency, 0)
        pct = 100.0 * count / len(trajectories)
        print(f"  {urgency:10s}: {count:5d} ({pct:5.1f}%)")
    print()
    print("Index entries:", len(index))
    print("Done.")


if __name__ == "__main__":
    generate()
