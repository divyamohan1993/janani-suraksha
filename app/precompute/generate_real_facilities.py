"""Fetch real facility and blood bank data from data.gov.in for all Indian states.

Fetches from two resources:
- 37670b6f-c236-49a7-8cd7-cc2dc610e32d: ~30,284 hospitals with geocoordinates
- fced6df9-a360-4e08-8ca0-f283fc74ce15: ~2,823 blood banks with lat/lng

Run as: python -m app.precompute.generate_real_facilities
"""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_GOV_API_KEY = os.environ.get("DATA_GOV_API_KEY", "")
_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data"

HOSPITAL_RESOURCE_ID = "37670b6f-c236-49a7-8cd7-cc2dc610e32d"
BLOOD_BANK_RESOURCE_ID = "fced6df9-a360-4e08-8ca0-f283fc74ce15"
PAGE_SIZE = 500

STATES = [
    # 28 States
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    # Union Territories
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]


def clean(val):
    if not val or str(val).strip().lower() in ("na", "n/a", "nil", "none", "-", "0"):
        return ""
    return str(val).strip()


def parse_location_coordinates(coord_str: str) -> tuple[float, float] | None:
    """Parse _location_coordinates field ('lat, lng' string)."""
    if not coord_str or not isinstance(coord_str, str):
        return None
    try:
        parts = coord_str.split(",")
        if len(parts) != 2:
            return None
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
        if not (6.0 <= lat <= 37.0 and 68.0 <= lng <= 98.0):
            return None
        return lat, lng
    except (ValueError, TypeError):
        return None


def fetch_hospitals_paginated() -> dict[str, list[dict]]:
    """Fetch all hospitals with pagination, organized by state.

    Extracts coordinates from _location_coordinates field.
    """
    all_facilities: dict[str, list[dict]] = {}
    offset = 0
    total_fetched = 0

    print(f"Fetching hospitals from resource {HOSPITAL_RESOURCE_ID} (paginated)...")

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
                raise RuntimeError(f"Failed to fetch hospital data: {e}")
            break

        records = data.get("records", [])
        if not records:
            break

        for r in records:
            name = clean(r.get("Hospital_Name") or r.get("hospital_name", ""))
            if not name:
                continue

            state = clean(r.get("State") or r.get("state", ""))
            if not state:
                continue

            # Parse coordinates
            coord_str = r.get("_location_coordinates") or r.get("location_coordinates") or ""
            coords = parse_location_coordinates(coord_str)

            facility = {
                "name": name,
                "category": clean(r.get("Hospital_Category") or r.get("hospital_category", "")) or "General",
                "care_type": clean(r.get("Hospital_Care_Type") or r.get("hospital_care_type", "")),
                "address": clean(r.get("Address_Original_First_Line") or r.get("_address_original_first_line", "")),
                "district": clean(r.get("District") or r.get("district", "")),
                "pincode": clean(r.get("Pincode") or r.get("pincode", "")),
                "phone": clean(r.get("Telephone") or r.get("telephone", "")),
                "emergency_phone": clean(r.get("Emergency_Num") or r.get("emergency_num", "")),
                "specialties": clean(r.get("Specialties") or r.get("specialties", "")),
                "beds": clean(r.get("Total_Num_Beds") or r.get("total_num_beds", "")),
                "doctors": clean(r.get("Number_Doctor") or r.get("number_doctor", "")),
                "bloodbank_phone": clean(r.get("Bloodbank_Phone_No") or r.get("bloodbank_phone_no", "")),
            }

            if coords:
                facility["latitude"] = round(coords[0], 6)
                facility["longitude"] = round(coords[1], 6)

            if state not in all_facilities:
                all_facilities[state] = []
            all_facilities[state].append(facility)

        total_fetched += len(records)
        total_count = data.get("total", 0)
        offset += PAGE_SIZE
        print(f"  Fetched offset={offset - PAGE_SIZE}: {len(records)} records (total so far: {total_fetched})")

        if offset >= total_count or len(records) < PAGE_SIZE:
            break

        time.sleep(0.3)

    # Deduplicate per state
    for state in all_facilities:
        seen = set()
        unique = []
        for f in all_facilities[state]:
            key = f["name"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(f)
        all_facilities[state] = unique

    return all_facilities


def fetch_blood_banks_paginated() -> list[dict]:
    """Fetch all blood banks from data.gov.in with pagination.

    Resource fced6df9-a360-4e08-8ca0-f283fc74ce15 has Latitude/Longitude fields.
    """
    blood_banks = []
    offset = 0
    total_fetched = 0

    print(f"\nFetching blood banks from resource {BLOOD_BANK_RESOURCE_ID} (paginated)...")

    while True:
        url = (
            f"https://api.data.gov.in/resource/{BLOOD_BANK_RESOURCE_ID}"
            f"?api-key={DATA_GOV_API_KEY}&format=json"
            f"&limit={PAGE_SIZE}&offset={offset}"
        )

        try:
            resp = urllib.request.urlopen(url, timeout=60)
            data = json.loads(resp.read())
        except Exception as e:
            print(f"  API request failed at offset {offset}: {e}")
            if offset == 0:
                print(f"  WARNING: Could not fetch blood bank data: {e}")
                return []
            break

        records = data.get("records", [])
        if not records:
            break

        for r in records:
            name = clean(
                r.get("Blood_Bank_Name")
                or r.get("blood_bank_name")
                or r.get("_blood_bank_name")
                or ""
            )
            if not name:
                continue

            # Parse lat/lng from separate fields
            lat_str = str(r.get("Latitude") or r.get("latitude") or "").strip()
            lng_str = str(r.get("Longitude") or r.get("longitude") or "").strip()

            latitude = None
            longitude = None
            try:
                lat_val = float(lat_str)
                lng_val = float(lng_str)
                if 6.0 <= lat_val <= 37.0 and 68.0 <= lng_val <= 98.0:
                    latitude = round(lat_val, 6)
                    longitude = round(lng_val, 6)
            except (ValueError, TypeError):
                pass

            state = clean(r.get("State") or r.get("state") or "")
            district = clean(r.get("District") or r.get("district") or "")
            contact = clean(r.get("Contact_No") or r.get("contact_no") or "")
            category = clean(r.get("Category") or r.get("category") or "")
            components = clean(
                r.get("Blood_Component_Available")
                or r.get("blood_component_available")
                or ""
            )
            service_time = clean(r.get("Service_Time") or r.get("service_time") or "")
            address = clean(r.get("Address") or r.get("address") or "")
            pincode = clean(r.get("Pincode") or r.get("pincode") or "")

            bank = {
                "name": name,
                "state": state,
                "district": district,
                "address": address,
                "pincode": pincode,
                "contact": contact,
                "category": category,
                "components_available": components,
                "service_time": service_time,
            }

            if latitude is not None:
                bank["latitude"] = latitude
                bank["longitude"] = longitude

            blood_banks.append(bank)

        total_fetched += len(records)
        total_count = data.get("total", 0)
        offset += PAGE_SIZE
        print(f"  Fetched offset={offset - PAGE_SIZE}: {len(records)} records (total so far: {total_fetched})")

        if offset >= total_count or len(records) < PAGE_SIZE:
            break

        time.sleep(0.3)

    # Deduplicate
    seen = set()
    unique = []
    for b in blood_banks:
        key = b["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(b)

    return unique


def main():
    if not DATA_GOV_API_KEY:
        # Check for existing data
        facilities_path = _OUTPUT_DIR / "real_facilities.json"
        blood_banks_path = _OUTPUT_DIR / "real_blood_banks.json"
        if facilities_path.exists():
            print(f"DATA_GOV_API_KEY not set -- using existing {facilities_path} "
                  f"({facilities_path.stat().st_size / 1024:.0f} KB)")
            if blood_banks_path.exists():
                print(f"  Also found existing {blood_banks_path} "
                      f"({blood_banks_path.stat().st_size / 1024:.0f} KB)")
            raise SystemExit(0)
        raise RuntimeError(
            "DATA_GOV_API_KEY environment variable is required but not set and no existing "
            "data found. Get an API key from https://data.gov.in."
        )

    print("Fetching real facility and blood bank data from data.gov.in...")
    print(f"API Key: {DATA_GOV_API_KEY[:10]}...")
    print()

    # --- Fetch hospitals ---
    all_facilities = fetch_hospitals_paginated()
    total_facilities = sum(len(v) for v in all_facilities.values())
    geocoded = sum(
        1 for facs in all_facilities.values()
        for f in facs if "latitude" in f
    )

    facilities_path = _OUTPUT_DIR / "real_facilities.json"
    facilities_path.parent.mkdir(parents=True, exist_ok=True)
    with open(facilities_path, "w") as f:
        json.dump(all_facilities, f, separators=(",", ":"))

    size_kb = facilities_path.stat().st_size / 1024
    print(f"\nHospitals: {total_facilities} across {len(all_facilities)} states")
    print(f"  Geocoded (with coordinates): {geocoded}")
    print(f"  Saved to {facilities_path} ({size_kb:.1f} KB)")

    # --- Fetch blood banks ---
    blood_banks = fetch_blood_banks_paginated()
    geocoded_bb = sum(1 for b in blood_banks if "latitude" in b)

    blood_banks_path = _OUTPUT_DIR / "real_blood_banks.json"
    with open(blood_banks_path, "w") as f:
        json.dump(blood_banks, f, separators=(",", ":"))

    size_kb_bb = blood_banks_path.stat().st_size / 1024
    print(f"\nBlood Banks: {len(blood_banks)} total")
    print(f"  Geocoded (with coordinates): {geocoded_bb}")
    print(f"  Saved to {blood_banks_path} ({size_kb_bb:.1f} KB)")

    print(f"\nDone. All data sourced from data.gov.in API.")


if __name__ == "__main__":
    main()
