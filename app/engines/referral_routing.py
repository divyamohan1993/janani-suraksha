import json
import math
from typing import Optional


class ReferralRoutingEngine:
    """O(1) emergency referral routing via precomputed facility-capability spatial index.

    Precomputed nearest-facility lookup tables per capability level, using haversine
    distance on a 0.1-degree grid (~11km cells). Grid-key lookup enables instant
    optimal facility recommendation. Backup facilities are also precomputed for O(1)
    fallback routing.

    Data source: data.gov.in hospital registry (resource 37670b6f-c236-49a7-8cd7-cc2dc610e32d).
    """

    # Capability levels (hierarchical)
    CAPABILITIES = [
        "basic_emoc",
        "comprehensive_emoc",
        "blood_transfusion",
        "c_section",
        "neonatal_icu",
    ]

    def __init__(self):
        self._facilities: list[dict] = []
        self._spt: dict[str, dict[str, dict]] = {}  # capability -> grid_key -> facility
        self._loaded = False

    def load(self, path: str) -> None:
        """Load precomputed facility graph and SPTs from JSON."""
        with open(path) as f:
            data = json.load(f)
        self._facilities = data["facilities"]
        self._spt = data["shortest_path_trees"]
        self._loaded = True

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in km between two lat/lon points."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))

    @staticmethod
    def _grid_key(lat: float, lon: float) -> str:
        """Convert lat/lon to grid cell key (0.1 degree resolution ~11km cells)."""
        return f"{lat:.1f},{lon:.1f}"

    def route(
        self,
        latitude: float,
        longitude: float,
        capability_required: str,
        risk_level: str = "high",
    ) -> dict:
        """O(1) facility lookup via precomputed shortest-path tree.

        Both primary and backup facility lookups are O(1) -- the backup is
        precomputed as the 2nd-nearest facility in each grid cell.

        Returns dict with: facility_name, facility_type, distance_km, eta_minutes,
        specialist_available, blood_bank_status, has_functional_ot, contact_phone, backup_facility
        """
        grid = self._grid_key(latitude, longitude)

        # O(1) lookup in precomputed SPT
        if capability_required in self._spt and grid in self._spt[capability_required]:
            result = self._spt[capability_required][grid].copy()
            # Recalculate exact distance from actual coordinates
            result["distance_km"] = round(
                self._haversine(
                    latitude, longitude, result["latitude"], result["longitude"]
                ),
                1,
            )
            # ETA assumes ~30 km/h average rural ambulance speed (distance_km * 2.0 min/km)
            # Thaddeus S, Maine D, "Too far to walk: maternal mortality in context",
            # Soc Sci Med 1994;38(8):1091-1110. Avg rural ambulance speed in India
            # 25-35 km/h per NRHM Emergency Response reports.
            result["eta_minutes"] = round(
                result["distance_km"] * 2.0, 0
            )

            # O(1) backup facility lookup from precomputed 2nd-nearest
            backup_data = result.pop("backup", None)
            if backup_data:
                backup_dist = round(
                    self._haversine(
                        latitude, longitude,
                        backup_data["latitude"], backup_data["longitude"]
                    ),
                    1,
                )
                result["backup_facility"] = {
                    "facility_name": backup_data["facility_name"],
                    "facility_type": backup_data["facility_type"],
                    "distance_km": backup_dist,
                    "eta_minutes": round(backup_dist * 2.0, 0),
                }
            else:
                result["backup_facility"] = None

            # Remove internal fields
            result.pop("latitude", None)
            result.pop("longitude", None)
            result.pop("facility_id", None)

            return result

        # Fallback: linear scan (should not happen with complete SPT)
        return self._find_nearest(latitude, longitude, capability_required)

    def _find_nearest(self, lat: float, lon: float, capability: str) -> dict:
        """Linear scan fallback for finding nearest facility with capability."""
        best = None
        best_dist = float("inf")

        for facility in self._facilities:
            if capability not in facility.get("capabilities", []):
                continue
            dist = self._haversine(
                lat, lon, facility["latitude"], facility["longitude"]
            )
            if dist < best_dist:
                best_dist = dist
                best = facility

        if best is None:
            return {
                "facility_name": "No facility available",
                "facility_type": "unknown",
                "distance_km": 0,
                "eta_minutes": 0,
                "specialist_available": False,
                "blood_bank_status": "unavailable",
                "has_functional_ot": False,
                "contact_phone": "108",
                "backup_facility": None,
            }

        return {
            "facility_name": best["name"],
            "facility_type": best["type"],
            "distance_km": round(best_dist, 1),
            "eta_minutes": round(best_dist * 2.0, 0),  # ~30 km/h; Thaddeus & Maine 1994 + NRHM reports
            "specialist_available": best.get("specialist_available", False),
            "blood_bank_status": best.get("blood_bank_status", "unavailable"),
            "has_functional_ot": best.get("has_functional_ot", False),
            "contact_phone": best.get("contact_phone", "108"),
            "backup_facility": None,
        }

    def get_all_facilities(self) -> list[dict]:
        """Return all facilities for dashboard display."""
        return self._facilities

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def facility_count(self) -> int:
        return len(self._facilities)
