"""Fetch real facility data from data.gov.in for all Indian states."""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_GOV_API_KEY = os.environ.get("DATA_GOV_API_KEY")
if not DATA_GOV_API_KEY:
    raise RuntimeError(
        "DATA_GOV_API_KEY environment variable is required but not set. "
        "Get an API key from https://data.gov.in and set it before running this script."
    )
RESOURCES = [
    "7d208ae4-5d65-47ec-8cb8-2a7a7ac89f8c",
    "37670b6f-c236-49a7-8cd7-cc2dc610e32d",
]
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
    if not val or val == "NA":
        return ""
    return val.strip()


def fetch_state(state: str) -> list[dict]:
    facilities = []
    for resource_id in RESOURCES:
        url = (
            f"https://api.data.gov.in/resource/{resource_id}"
            f"?api-key={DATA_GOV_API_KEY}&format=json&limit=500"
            f"&filters%5Bstate%5D={urllib.parse.quote(state)}"
        )
        try:
            resp = urllib.request.urlopen(url, timeout=30)
            data = json.loads(resp.read())
            for r in data.get("records", []):
                name = clean(r.get("hospitalname") or r.get("hospital_name", ""))
                if not name:
                    continue
                facilities.append({
                    "name": name,
                    "category": clean(r.get("hospital_category", "")) or "General",
                    "care_type": clean(
                        r.get("hostipalcaretype") or
                        r.get("_hospital_care_type", "")),
                    "address": clean(
                        r.get("address_first_line") or
                        r.get("_address_original_first_line", "")),
                    "district": clean(r.get("district", "")),
                    "pincode": clean(r.get("_pincode") or r.get("pincode", "")),
                    "phone": clean(
                        r.get("telephone") or r.get("mobile_number", "")),
                    "emergency_phone": clean(
                        r.get("emergencynum") or r.get("emergency_num", "")),
                    "specialties": clean(r.get("specialties", "")),
                })
        except Exception as e:
            print(f"  Warning: {resource_id} failed for {state}: {e}")
    # Deduplicate
    seen = set()
    unique = []
    for f in facilities:
        key = f["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def main():
    print("Fetching real facility data from data.gov.in...")
    print(f"API Key: {DATA_GOV_API_KEY[:10]}...")
    print(f"States: {len(STATES)}")
    print()

    all_facilities = {}
    total = 0

    for state in STATES:
        facilities = fetch_state(state)
        if facilities:
            all_facilities[state] = facilities
            total += len(facilities)
        print(f"  {state}: {len(facilities)} facilities")
        time.sleep(0.3)

    out_path = Path(__file__).parent.parent.parent / "data" / "real_facilities.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_facilities, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"\nTotal: {total} facilities across {len(all_facilities)} states")
    print(f"Saved to {out_path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
