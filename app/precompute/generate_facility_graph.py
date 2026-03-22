"""Fetch real hospital data from data.gov.in and build precomputed spatial index.

Uses resource 37670b6f-c236-49a7-8cd7-cc2dc610e32d which contains ~30,284
hospitals with geocoordinates in the _location_coordinates field.

Run as: python -m app.precompute.generate_facility_graph
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

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

        try:
            resp = urllib.request.urlopen(url, timeout=60)
            data = json.loads(resp.read())
        except Exception as e:
            print(f"  API request failed at offset {offset}: {e}")
            if offset == 0:
                raise RuntimeError(
                    f"Failed to fetch any data from data.gov.in: {e}. "
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


def precompute_shortest_path_trees(
    facilities: list[dict],
) -> dict[str, dict[str, dict]]:
    """Build shortest-path trees: for each capability, map every grid cell
    to its nearest AND second-nearest facility (backup).

    Grid covers all of India at 0.1-degree resolution (~11 km cells).
    Only populates cells that have facilities within 200 km.
    """
    # Compute bounding box from actual facility coordinates
    lats = [f["latitude"] for f in facilities]
    lons = [f["longitude"] for f in facilities]

    if not lats:
        return {}

    lat_min = round(min(lats) - 0.5, 1)
    lat_max = round(max(lats) + 0.5, 1)
    lon_min = round(min(lons) - 0.5, 1)
    lon_max = round(max(lons) + 0.5, 1)

    # Generate grid cell centers
    grid_lats = []
    lat = lat_min
    while lat <= lat_max + 0.05:
        grid_lats.append(round(lat, 1))
        lat = round(lat + 0.1, 1)

    grid_lons = []
    lon = lon_min
    while lon <= lon_max + 0.05:
        grid_lons.append(round(lon, 1))
        lon = round(lon + 0.1, 1)

    spt: dict[str, dict[str, dict]] = {}

    for capability in ALL_CAPABILITIES:
        capable = [f for f in facilities if capability in f.get("capabilities", [])]
        if not capable:
            continue

        print(f"  Building SPT for {capability}: {len(capable)} facilities, "
              f"{len(grid_lats)}x{len(grid_lons)} grid")

        spt[capability] = {}

        for glat in grid_lats:
            for glon in grid_lons:
                gk = grid_key(glat, glon)

                # Find nearest and second-nearest facility
                best = None
                best_dist = float("inf")
                second = None
                second_dist = float("inf")

                for fac in capable:
                    dist = haversine(glat, glon, fac["latitude"], fac["longitude"])
                    if dist < best_dist:
                        second = best
                        second_dist = best_dist
                        best = fac
                        best_dist = dist
                    elif dist < second_dist:
                        second = fac
                        second_dist = dist

                # Only store if nearest is within 200 km
                if best is not None and best_dist <= 200:
                    entry = {
                        "facility_id": best["facility_id"],
                        "facility_name": best["name"],
                        "facility_type": best["type"],
                        "latitude": best["latitude"],
                        "longitude": best["longitude"],
                        "distance_km": round(best_dist, 1),
                        "eta_minutes": round(best_dist * 2.0, 0),
                        "specialist_available": best.get("specialist_available", False),
                        "blood_bank_status": best.get("blood_bank_status", "unavailable"),
                        "has_functional_ot": best.get("has_functional_ot", False),
                        "contact_phone": best.get("contact_phone", "108"),
                    }

                    # Precompute backup facility (2nd nearest) for O(1) backup lookup
                    if second is not None and second_dist <= 300:
                        entry["backup"] = {
                            "facility_id": second["facility_id"],
                            "facility_name": second["name"],
                            "facility_type": second["type"],
                            "latitude": second["latitude"],
                            "longitude": second["longitude"],
                            "distance_km": round(second_dist, 1),
                            "eta_minutes": round(second_dist * 2.0, 0),
                        }

                    spt[capability][gk] = entry

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
