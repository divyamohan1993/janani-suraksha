"""Fetch real hospital data from data.gov.in and build precomputed spatial index.

Uses resource 37670b6f-c236-49a7-8cd7-cc2dc610e32d which contains ~28,128
hospitals total, of which ~10,602 have valid geocoordinates for spatial indexing.

Run as: python -m app.precompute.generate_facility_graph
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np

# --- data.gov.in API config ---
DATA_GOV_API_KEY = os.environ.get("DATA_GOV_API_KEY", "")
HOSPITAL_RESOURCE_ID = "37670b6f-c236-49a7-8cd7-cc2dc610e32d"
PAGE_SIZE = 500

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

# Mapping from Hospital_Category field values to internal type codes
CATEGORY_MAP = {
    "government hospital": "district_hospital",
    "govt hospital": "district_hospital",
    "district hospital": "district_hospital",
    "civil hospital": "district_hospital",
    "general hospital": "district_hospital",
    "medical college": "medical_college",
    "medical college hospital": "medical_college",
    "teaching hospital": "medical_college",
    "community health centre": "chc",
    "community health center": "chc",
    "chc": "chc",
    "primary health centre": "phc",
    "primary health center": "phc",
    "phc": "phc",
    "sub centre": "sub_centre",
    "sub center": "sub_centre",
    "sub-centre": "sub_centre",
    "health sub centre": "sub_centre",
    "private hospital": "district_hospital",
    "charitable hospital": "district_hospital",
    "railway hospital": "district_hospital",
    "esi hospital": "district_hospital",
    "cantonment hospital": "district_hospital",
    "municipal hospital": "district_hospital",
}


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


def parse_coordinates(coord_str: str) -> tuple[float, float] | None:
    """Parse _location_coordinates field ('lat, lng' string) to (lat, lng) floats.

    Returns None if parsing fails or coordinates are outside India's bounding box.
    """
    if not coord_str or not isinstance(coord_str, str):
        return None
    try:
        parts = coord_str.split(",")
        if len(parts) != 2:
            return None
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
        # Validate: must be within India's bounding box (roughly)
        if not (6.0 <= lat <= 37.0 and 68.0 <= lng <= 98.0):
            return None
        return lat, lng
    except (ValueError, TypeError):
        return None


def classify_hospital(record: dict) -> str:
    """Determine facility type from Hospital_Category and other fields."""
    category = (record.get("Hospital_Category") or record.get("hospital_category") or "").strip().lower()
    care_type = (record.get("Hospital_Care_Type") or record.get("hospital_care_type") or "").strip().lower()
    name = (record.get("Hospital_Name") or record.get("hospital_name") or "").strip().lower()

    # Try direct category mapping
    if category in CATEGORY_MAP:
        return CATEGORY_MAP[category]

    # Try partial matching on category
    for key, val in CATEGORY_MAP.items():
        if key in category:
            return val

    # Infer from name
    name_hints = {
        "medical college": "medical_college",
        "teaching hospital": "medical_college",
        "district hospital": "district_hospital",
        "civil hospital": "district_hospital",
        "chc": "chc",
        "community health": "chc",
        "phc": "phc",
        "primary health": "phc",
        "sub centre": "sub_centre",
        "sub center": "sub_centre",
    }
    for hint, ftype in name_hints.items():
        if hint in name:
            return ftype

    # Infer from care type
    if "super" in care_type or "multispecial" in care_type:
        return "medical_college"
    if "general" in care_type or "multi" in care_type:
        return "district_hospital"

    # Default to district_hospital for unclassified
    return "district_hospital"


def determine_blood_bank_status(record: dict) -> str:
    """Determine blood bank availability from Bloodbank_Phone_No field."""
    phone = (
        record.get("Bloodbank_Phone_No")
        or record.get("bloodbank_phone_no")
        or ""
    ).strip()
    if phone and phone.lower() not in ("na", "n/a", "-", "0", "nil", "none", ""):
        return "available"
    return "unavailable"


def determine_specialist(record: dict) -> bool:
    """Determine specialist availability from Number_Doctor field."""
    doctors = record.get("Number_Doctor") or record.get("number_doctor") or ""
    if isinstance(doctors, str):
        doctors = doctors.strip()
    try:
        return int(doctors) >= 3
    except (ValueError, TypeError):
        return False


def get_beds(record: dict) -> int:
    """Extract bed count from Total_Num_Beds field."""
    beds = record.get("Total_Num_Beds") or record.get("total_num_beds") or "0"
    if isinstance(beds, str):
        beds = beds.strip()
    try:
        return max(0, int(beds))
    except (ValueError, TypeError):
        return 0


def clean_phone(val: str) -> str:
    """Clean phone field."""
    if not val or val.strip().lower() in ("na", "n/a", "-", "0", "nil", "none"):
        return ""
    return val.strip()


def fetch_all_hospitals() -> list[dict]:
    """Fetch all hospitals from data.gov.in with pagination.

    Returns list of facility dicts with parsed coordinates and standardized fields.
    """
    if not DATA_GOV_API_KEY:
        raise RuntimeError(
            "DATA_GOV_API_KEY environment variable is required. "
            "Get an API key from https://data.gov.in. "
            "NO synthetic data fallback is available."
        )

    facilities = []
    offset = 0
    total_fetched = 0
    seen_names = set()

    print(f"Fetching hospitals from data.gov.in resource {HOSPITAL_RESOURCE_ID}...")
    print(f"API Key: {DATA_GOV_API_KEY[:10]}...")

    while True:
        url = (
            f"https://api.data.gov.in/resource/{HOSPITAL_RESOURCE_ID}"
            f"?api-key={DATA_GOV_API_KEY}&format=json"
            f"&limit={PAGE_SIZE}&offset={offset}"
        )

        data = None
        for attempt in range(5):
            try:
                resp = urllib.request.urlopen(url, timeout=120)
                data = json.loads(resp.read())
                break
            except Exception as e:
                wait = 2 ** attempt * 3
                print(f"  Attempt {attempt + 1}/5 failed at offset {offset}: {e}. Retrying in {wait}s...")
                time.sleep(wait)
        if data is None:
            print(f"  All retries exhausted at offset {offset}")
            if offset == 0:
                raise RuntimeError(
                    f"Failed to fetch any data from data.gov.in after 5 retries. "
                    "Cannot proceed without real data."
                )
            break

        records = data.get("records", [])
        if not records:
            break

        batch_valid = 0
        for record in records:
            # Parse coordinates from _location_coordinates
            coord_str = (
                record.get("_location_coordinates")
                or record.get("location_coordinates")
                or ""
            )
            coords = parse_coordinates(coord_str)
            if coords is None:
                continue

            lat, lng = coords

            name = (
                record.get("Hospital_Name")
                or record.get("hospital_name")
                or ""
            ).strip()
            if not name:
                continue

            # Deduplicate by name + coordinates
            dedup_key = f"{name.lower()}|{lat:.4f}|{lng:.4f}"
            if dedup_key in seen_names:
                continue
            seen_names.add(dedup_key)

            ftype = classify_hospital(record)
            capabilities = CAPABILITIES_BY_TYPE.get(ftype, []).copy()
            blood_status = determine_blood_bank_status(record)
            specialist = determine_specialist(record)
            beds = get_beds(record)

            # If blood bank phone is present and facility type supports it, add capability
            if blood_status == "available" and "blood_transfusion" not in capabilities:
                if ftype in ("district_hospital", "medical_college"):
                    capabilities.append("blood_transfusion")

            state = (record.get("State") or record.get("state") or "").strip()
            district = (record.get("District") or record.get("district") or "").strip()
            pincode = (record.get("Pincode") or record.get("pincode") or "").strip()
            phone = clean_phone(
                record.get("Telephone") or record.get("telephone") or ""
            )
            emergency = clean_phone(
                record.get("Emergency_Num") or record.get("emergency_num") or ""
            )
            specialties = (
                record.get("Specialties") or record.get("specialties") or ""
            ).strip()

            # Functional OT: infer from care type and specialties
            has_ot = ftype in ("district_hospital", "medical_college")
            if ftype == "chc" and ("surgery" in specialties.lower() or "ortho" in specialties.lower()):
                has_ot = True

            facility_id = f"DGOV-{len(facilities) + 1:05d}"

            facilities.append({
                "facility_id": facility_id,
                "name": name,
                "type": ftype,
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "capabilities": capabilities,
                "specialist_available": specialist,
                "blood_bank_status": blood_status,
                "has_functional_ot": has_ot,
                "beds_available": beds,
                "contact_phone": emergency or phone or "108",
                "state": state,
                "district": district,
                "pincode": pincode,
                "specialties": specialties,
            })
            batch_valid += 1

        total_fetched += len(records)
        print(f"  Fetched offset={offset}: {len(records)} records, {batch_valid} valid with coordinates")

        # Check if we've fetched all
        total_count = data.get("total", 0)
        offset += PAGE_SIZE

        if offset >= total_count or len(records) < PAGE_SIZE:
            break

        time.sleep(0.3)  # Rate limiting

    print(f"  Total API records fetched: {total_fetched}")
    print(f"  Valid facilities with coordinates: {len(facilities)}")
    return facilities


def grid_key(lat: float, lon: float) -> str:
    """Convert lat/lon to grid cell key (0.1 degree resolution)."""
    return f"{lat:.1f},{lon:.1f}"


def haversine_vectorized(
    grid_lats: np.ndarray, grid_lons: np.ndarray,
    fac_lats: np.ndarray, fac_lons: np.ndarray,
) -> np.ndarray:
    """Vectorized haversine: returns distance matrix (n_grid, n_fac) in km."""
    R = 6371.0
    glat_r = np.radians(grid_lats)[:, None]
    glon_r = np.radians(grid_lons)[:, None]
    flat_r = np.radians(fac_lats)[None, :]
    flon_r = np.radians(fac_lons)[None, :]

    dlat = flat_r - glat_r
    dlon = flon_r - glon_r
    a = np.sin(dlat / 2) ** 2 + np.cos(glat_r) * np.cos(flat_r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def precompute_shortest_path_trees(
    facilities: list[dict],
) -> dict[str, dict[str, dict]]:
    """Build shortest-path trees: for each capability, map every grid cell
    to its nearest AND second-nearest facility (backup).

    Grid covers all of India at 0.1-degree resolution (~11 km cells).
    Only populates cells that have facilities within 200 km.

    Uses numpy vectorized haversine for performance.
    """
    lats = [f["latitude"] for f in facilities]
    lons = [f["longitude"] for f in facilities]

    if not lats:
        return {}

    lat_min = round(min(lats) - 0.5, 1)
    lat_max = round(max(lats) + 0.5, 1)
    lon_min = round(min(lons) - 0.5, 1)
    lon_max = round(max(lons) + 0.5, 1)

    grid_lats_list = np.arange(lat_min, lat_max + 0.05, 0.1).round(1)
    grid_lons_list = np.arange(lon_min, lon_max + 0.05, 0.1).round(1)

    # Build full grid (n_grid, 2)
    glat_mesh, glon_mesh = np.meshgrid(grid_lats_list, grid_lons_list, indexing="ij")
    grid_lats_flat = glat_mesh.ravel()
    grid_lons_flat = glon_mesh.ravel()
    n_grid = len(grid_lats_flat)

    spt: dict[str, dict[str, dict]] = {}

    for capability in ALL_CAPABILITIES:
        capable = [f for f in facilities if capability in f.get("capabilities", [])]
        if not capable:
            continue

        n_fac = len(capable)
        print(f"  Building SPT for {capability}: {n_fac} facilities, "
              f"{len(grid_lats_list)}x{len(grid_lons_list)} grid ({n_grid} cells)")

        fac_lats = np.array([f["latitude"] for f in capable])
        fac_lons = np.array([f["longitude"] for f in capable])

        # Process in chunks to limit memory (~500 MB max)
        CHUNK = max(1, min(n_grid, 50_000_000 // max(n_fac, 1)))
        spt[capability] = {}

        for start in range(0, n_grid, CHUNK):
            end = min(start + CHUNK, n_grid)
            g_lats_chunk = grid_lats_flat[start:end]
            g_lons_chunk = grid_lons_flat[start:end]

            # (chunk_size, n_fac) distance matrix
            dists = haversine_vectorized(g_lats_chunk, g_lons_chunk, fac_lats, fac_lons)

            # Find nearest and second-nearest per grid cell
            if n_fac >= 2:
                idx2 = np.argpartition(dists, 2, axis=1)[:, :2]
                rows = np.arange(end - start)[:, None]
                d2 = dists[rows, idx2]
                # Sort the two so col 0 is nearest
                order = np.argsort(d2, axis=1)
                idx2_sorted = np.take_along_axis(idx2, order, axis=1)
                d2_sorted = np.take_along_axis(d2, order, axis=1)
                best_idx = idx2_sorted[:, 0]
                best_dist = d2_sorted[:, 0]
                second_idx = idx2_sorted[:, 1]
                second_dist = d2_sorted[:, 1]
            else:
                best_idx = np.zeros(end - start, dtype=int)
                best_dist = dists[:, 0]
                second_idx = None
                second_dist = None

            for i in range(end - start):
                if best_dist[i] > 200:
                    continue

                glat = round(float(g_lats_chunk[i]), 1)
                glon = round(float(g_lons_chunk[i]), 1)
                gk = grid_key(glat, glon)
                best = capable[int(best_idx[i])]

                entry = {
                    "facility_id": best["facility_id"],
                    "facility_name": best["name"],
                    "facility_type": best["type"],
                    "latitude": best["latitude"],
                    "longitude": best["longitude"],
                    "distance_km": round(float(best_dist[i]), 1),
                    "eta_minutes": round(float(best_dist[i]) * 2.0, 0),
                    "specialist_available": best.get("specialist_available", False),
                    "blood_bank_status": best.get("blood_bank_status", "unavailable"),
                    "has_functional_ot": best.get("has_functional_ot", False),
                    "contact_phone": best.get("contact_phone", "108"),
                }

                if second_idx is not None and second_dist[i] <= 300:
                    sec = capable[int(second_idx[i])]
                    entry["backup"] = {
                        "facility_id": sec["facility_id"],
                        "facility_name": sec["name"],
                        "facility_type": sec["type"],
                        "latitude": sec["latitude"],
                        "longitude": sec["longitude"],
                        "distance_km": round(float(second_dist[i]), 1),
                        "eta_minutes": round(float(second_dist[i]) * 2.0, 0),
                    }

                spt[capability][gk] = entry

        print(f"    → {len(spt[capability])} grid cells mapped")

    return spt


def main() -> None:
    print("=" * 60)
    print("Janani Suraksha - Real Facility Graph Generator")
    print("Source: data.gov.in (Government of India Open Data)")
    print("=" * 60)
    print()

    # Fetch real facilities from data.gov.in
    facilities = fetch_all_hospitals()

    if not facilities:
        raise RuntimeError(
            "No valid facilities fetched from data.gov.in. "
            "Cannot generate facility graph without real data."
        )

    # Print facility breakdown
    type_counts: dict[str, int] = {}
    for f in facilities:
        ftype = f["type"]
        type_counts[ftype] = type_counts.get(ftype, 0) + 1

    print(f"\n  Total facilities: {len(facilities)}")
    for ftype in [
        "medical_college",
        "district_hospital",
        "chc",
        "phc",
        "sub_centre",
    ]:
        print(f"    {ftype}: {type_counts.get(ftype, 0)}")

    # State breakdown
    state_counts: dict[str, int] = {}
    for f in facilities:
        st = f.get("state", "Unknown")
        state_counts[st] = state_counts.get(st, 0) + 1
    print(f"\n  States/UTs covered: {len(state_counts)}")

    # Capability counts
    print("\n  Capability coverage:")
    for cap in ALL_CAPABILITIES:
        count = sum(1 for f in facilities if cap in f.get("capabilities", []))
        print(f"    {cap}: {count} facilities")

    # Precompute SPTs
    print("\n  Precomputing shortest-path trees (with backup facilities)...")
    spt = precompute_shortest_path_trees(facilities)

    for cap, tree in spt.items():
        print(f"    {cap}: {len(tree)} grid cells mapped")

    # Build output
    output = {
        "facilities": facilities,
        "shortest_path_trees": spt,
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "data.gov.in",
            "resource_id": HOSPITAL_RESOURCE_ID,
            "facility_count": len(facilities),
            "grid_resolution_degrees": 0.1,
            "states_covered": len(state_counts),
            "has_precomputed_backups": True,
        },
    }

    # Write to data/facility_graph.json
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "facility_graph.json")

    with open(output_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n  Output written to: {output_path}")
    print(f"  File size: {file_size_mb:.2f} MB")
    print()
    print("=" * 60)
    print("Done. Real facility graph ready for O(1) referral routing.")
    print("=" * 60)


if __name__ == "__main__":
    main()
