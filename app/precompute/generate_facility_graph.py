"""Generate synthetic facility network for Sitapur district, Uttar Pradesh.

Produces a realistic health facility hierarchy with precomputed shortest-path
trees for O(1) referral routing lookups.

Run as: python -m app.precompute.generate_facility_graph
"""

import json
import math
import os
import random
from datetime import datetime, timezone

random.seed(42)

# --- Constants ---

# Sitapur district center
CENTER_LAT = 27.57
CENTER_LON = 80.68
SPREAD = 0.5  # degrees (~55 km)

# Block names in Sitapur district
BLOCKS = [
    "Sidhauli",
    "Mishrikh",
    "Biswan",
    "Mahmudabad",
    "Laharpur",
    "Kasmanda",
    "Behta",
    "Gondlamau",
    "Pahala",
    "Reusa",
    "Pisawan",
    "Ramkot",
    "Ailiya",
    "Machhrehta",
    "Sakran",
    "Khairabad",
    "Parsendi",
]

# Village-style suffixes for sub-centres
VILLAGE_SUFFIXES = [
    "pur",
    "ganj",
    "nagar",
    "garh",
    "khera",
    "patti",
    "gaon",
    "basti",
    "tola",
    "kalan",
    "khurd",
    "sarai",
    "kot",
    "ghat",
    "bagh",
]

VILLAGE_PREFIXES = [
    "Ram",
    "Shiv",
    "Mohan",
    "Lal",
    "Hari",
    "Devi",
    "Govind",
    "Pratap",
    "Bal",
    "Ganesh",
    "Lakshmi",
    "Durga",
    "Kashi",
    "Nand",
    "Bhola",
    "Suraj",
    "Chandra",
    "Indra",
    "Vijay",
    "Amar",
    "Jagdish",
    "Rajendra",
    "Sunder",
    "Madan",
    "Pyare",
]

# Capability definitions per facility type
CAPABILITIES_BY_TYPE = {
    "sub_centre": [],
    "phc": ["basic_emoc"],
    "chc": ["basic_emoc", "comprehensive_emoc"],
    "district_hospital": [
        "basic_emoc",
        "comprehensive_emoc",
        "blood_transfusion",
        "c_section",
    ],
    "medical_college": [
        "basic_emoc",
        "comprehensive_emoc",
        "blood_transfusion",
        "c_section",
        "neonatal_icu",
    ],
}

ALL_CAPABILITIES = [
    "basic_emoc",
    "comprehensive_emoc",
    "blood_transfusion",
    "c_section",
    "neonatal_icu",
]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def random_lat_lon() -> tuple[float, float]:
    """Generate a random lat/lon within Sitapur district bounds."""
    lat = CENTER_LAT + random.uniform(-SPREAD, SPREAD)
    lon = CENTER_LON + random.uniform(-SPREAD, SPREAD)
    return round(lat, 6), round(lon, 6)


def random_phone() -> str:
    """Generate a realistic Indian mobile number."""
    prefixes = ["70", "72", "73", "74", "75", "76", "77", "78", "79", "80", "81",
                "82", "83", "84", "85", "86", "87", "88", "89", "90", "91", "92",
                "93", "94", "95", "96", "97", "98", "99"]
    prefix = random.choice(prefixes)
    return f"+91-{prefix}{random.randint(10000000, 99999999)}"


def generate_village_name() -> str:
    """Generate a realistic Indian village name."""
    return random.choice(VILLAGE_PREFIXES) + random.choice(VILLAGE_SUFFIXES)


def generate_facilities() -> list[dict]:
    """Generate ~200 facilities with realistic hierarchy."""
    facilities = []
    used_village_names: set[str] = set()
    facility_counter = 0

    def next_id() -> str:
        nonlocal facility_counter
        facility_counter += 1
        return f"FAC-STP-{facility_counter:04d}"

    # --- 5 Medical Colleges ---
    mc_names = [
        "Government Medical College Sitapur",
        "Shri Ram Murti Smarak Medical College",
        "Prasad Institute of Medical Sciences Sitapur",
        "Maharishi Devanand Medical College Sitapur",
        "Dr. Ambedkar Memorial Medical College Sitapur",
    ]
    for name in mc_names:
        lat, lon = random_lat_lon()
        # Medical colleges cluster closer to district center
        lat = CENTER_LAT + random.uniform(-0.15, 0.15)
        lon = CENTER_LON + random.uniform(-0.15, 0.15)
        facilities.append({
            "facility_id": next_id(),
            "name": name,
            "type": "medical_college",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "capabilities": CAPABILITIES_BY_TYPE["medical_college"].copy(),
            "specialist_available": random.random() < 0.95,
            "blood_bank_status": random.choice(["available", "available", "low_stock"]),
            "has_functional_ot": True,
            "beds_available": random.randint(50, 200),
            "contact_phone": random_phone(),
        })

    # --- 10 District Hospitals ---
    dh_blocks = random.sample(BLOCKS, 10)
    for block in dh_blocks:
        lat, lon = random_lat_lon()
        lat = CENTER_LAT + random.uniform(-0.35, 0.35)
        lon = CENTER_LON + random.uniform(-0.35, 0.35)
        facilities.append({
            "facility_id": next_id(),
            "name": f"District Hospital {block}",
            "type": "district_hospital",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "capabilities": CAPABILITIES_BY_TYPE["district_hospital"].copy(),
            "specialist_available": random.random() < 0.85,
            "blood_bank_status": random.choice(
                ["available", "available", "low_stock", "unavailable"]
            ),
            "has_functional_ot": random.random() < 0.9,
            "beds_available": random.randint(20, 100),
            "contact_phone": random_phone(),
        })

    # --- 20 CHCs ---
    for i in range(20):
        block = BLOCKS[i % len(BLOCKS)]
        lat, lon = random_lat_lon()
        caps = CAPABILITIES_BY_TYPE["chc"].copy()
        # ~40% of CHCs have blood transfusion
        if random.random() < 0.4:
            caps.append("blood_transfusion")
        facilities.append({
            "facility_id": next_id(),
            "name": f"CHC {block}" if i < len(BLOCKS) else f"CHC {block}-{i // len(BLOCKS) + 1}",
            "type": "chc",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "capabilities": caps,
            "specialist_available": random.random() < 0.55,
            "blood_bank_status": (
                random.choice(["available", "low_stock", "unavailable"])
                if "blood_transfusion" in caps
                else "unavailable"
            ),
            "has_functional_ot": random.random() < 0.6,
            "beds_available": random.randint(6, 30),
            "contact_phone": random_phone(),
        })

    # --- 45 PHCs ---
    for i in range(45):
        block = BLOCKS[i % len(BLOCKS)]
        village = generate_village_name()
        while village in used_village_names:
            village = generate_village_name()
        used_village_names.add(village)
        lat, lon = random_lat_lon()
        facilities.append({
            "facility_id": next_id(),
            "name": f"PHC {village}, {block}",
            "type": "phc",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "capabilities": CAPABILITIES_BY_TYPE["phc"].copy(),
            "specialist_available": random.random() < 0.25,
            "blood_bank_status": "unavailable",
            "has_functional_ot": random.random() < 0.15,
            "beds_available": random.randint(2, 10),
            "contact_phone": random_phone(),
        })

    # --- 120 Sub-centres ---
    for i in range(120):
        block = BLOCKS[i % len(BLOCKS)]
        village = generate_village_name()
        while village in used_village_names:
            village = generate_village_name()
        used_village_names.add(village)
        lat, lon = random_lat_lon()
        facilities.append({
            "facility_id": next_id(),
            "name": f"Sub-centre {village}, {block}",
            "type": "sub_centre",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "capabilities": [],
            "specialist_available": False,
            "blood_bank_status": "unavailable",
            "has_functional_ot": False,
            "beds_available": random.randint(0, 4),
            "contact_phone": random_phone(),
        })

    return facilities


def grid_key(lat: float, lon: float) -> str:
    """Convert lat/lon to grid cell key (0.1 degree resolution)."""
    return f"{lat:.1f},{lon:.1f}"


def precompute_shortest_path_trees(
    facilities: list[dict],
) -> dict[str, dict[str, dict]]:
    """Build shortest-path trees: for each capability, map every grid cell to its nearest facility.

    Grid covers the Sitapur district bounding box at 0.1-degree resolution (~11 km cells).
    """
    # Define grid bounds with some padding
    lat_min = CENTER_LAT - SPREAD - 0.2
    lat_max = CENTER_LAT + SPREAD + 0.2
    lon_min = CENTER_LON - SPREAD - 0.2
    lon_max = CENTER_LON + SPREAD + 0.2

    # Generate all grid cell centers
    grid_lats = []
    lat = round(lat_min, 1)
    while lat <= lat_max + 0.05:
        grid_lats.append(round(lat, 1))
        lat = round(lat + 0.1, 1)

    grid_lons = []
    lon = round(lon_min, 1)
    while lon <= lon_max + 0.05:
        grid_lons.append(round(lon, 1))
        lon = round(lon + 0.1, 1)

    spt: dict[str, dict[str, dict]] = {}

    for capability in ALL_CAPABILITIES:
        # Filter facilities that have this capability
        capable = [f for f in facilities if capability in f.get("capabilities", [])]
        if not capable:
            continue

        spt[capability] = {}

        for glat in grid_lats:
            for glon in grid_lons:
                gk = grid_key(glat, glon)

                # Find nearest facility with this capability
                best = None
                best_dist = float("inf")
                for fac in capable:
                    dist = haversine(glat, glon, fac["latitude"], fac["longitude"])
                    if dist < best_dist:
                        best_dist = dist
                        best = fac

                if best is not None:
                    spt[capability][gk] = {
                        "facility_id": best["facility_id"],
                        "facility_name": best["name"],
                        "facility_type": best["type"],
                        "latitude": best["latitude"],
                        "longitude": best["longitude"],
                        "distance_km": round(best_dist, 1),
                        "eta_minutes": round(best_dist * 2.0, 0),
                        "specialist_available": best.get("specialist_available", False),
                        "blood_bank_status": best.get(
                            "blood_bank_status", "unavailable"
                        ),
                        "has_functional_ot": best.get("has_functional_ot", False),
                        "contact_phone": best.get("contact_phone", "108"),
                    }

    return spt


def main() -> None:
    print("=" * 60)
    print("Janani Suraksha - Facility Graph Generator")
    print("District: Sitapur, Uttar Pradesh")
    print("=" * 60)
    print()

    # Generate facilities
    print("Generating facilities...")
    facilities = generate_facilities()

    # Print facility breakdown
    type_counts: dict[str, int] = {}
    for f in facilities:
        ftype = f["type"]
        type_counts[ftype] = type_counts.get(ftype, 0) + 1

    print(f"  Total facilities: {len(facilities)}")
    for ftype in [
        "medical_college",
        "district_hospital",
        "chc",
        "phc",
        "sub_centre",
    ]:
        print(f"    {ftype}: {type_counts.get(ftype, 0)}")

    # Capability counts
    print()
    print("Capability coverage:")
    for cap in ALL_CAPABILITIES:
        count = sum(1 for f in facilities if cap in f.get("capabilities", []))
        print(f"    {cap}: {count} facilities")

    # Precompute SPTs
    print()
    print("Precomputing shortest-path trees...")
    spt = precompute_shortest_path_trees(facilities)

    for cap, tree in spt.items():
        print(f"    {cap}: {len(tree)} grid cells mapped")

    # Build output
    output = {
        "facilities": facilities,
        "shortest_path_trees": spt,
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "district": "Sitapur",
            "state": "Uttar Pradesh",
            "facility_count": len(facilities),
            "grid_resolution_degrees": 0.1,
            "seed": 42,
        },
    }

    # Write to data/facility_graph.json
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "facility_graph.json")

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print()
    print(f"Output written to: {output_path}")
    print(f"File size: {file_size_mb:.2f} MB")
    print()
    print("=" * 60)
    print("Done. Facility graph ready for O(1) referral routing.")
    print("=" * 60)


if __name__ == "__main__":
    main()
