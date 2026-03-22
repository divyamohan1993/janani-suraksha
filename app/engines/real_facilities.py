"""Real facility data from data.gov.in + Google Maps geocoding for navigation."""
import json
import math
import logging
from pathlib import Path
from typing import Optional
import urllib.parse
import httpx

logger = logging.getLogger("janani.facilities")

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# State centroids for lat/lon → state lookup
INDIAN_STATES = [
    (28.6, 77.2, "Delhi"), (26.85, 80.95, "Uttar Pradesh"),
    (27.57, 80.68, "Uttar Pradesh"), (25.6, 85.1, "Bihar"),
    (22.6, 88.4, "West Bengal"), (19.1, 73.0, "Maharashtra"),
    (13.0, 77.6, "Karnataka"), (26.9, 75.8, "Rajasthan"),
    (23.3, 77.4, "Madhya Pradesh"), (11.0, 76.9, "Tamil Nadu"),
    (17.4, 78.5, "Telangana"), (10.9, 76.3, "Kerala"),
    (21.2, 81.1, "Chhattisgarh"), (23.0, 72.6, "Gujarat"),
    (20.3, 85.8, "Odisha"), (30.7, 76.8, "Punjab"),
    (26.1, 91.7, "Assam"), (23.6, 87.0, "Jharkhand"),
    (15.4, 74.0, "Goa"), (31.1, 77.2, "Himachal Pradesh"),
    (34.1, 74.8, "Jammu and Kashmir"), (30.3, 78.0, "Uttarakhand"),
    (25.5, 82.0, "Uttar Pradesh"), (27.2, 79.0, "Uttar Pradesh"),
    (26.4, 80.3, "Uttar Pradesh"), (15.3, 75.7, "Karnataka"),
    (22.3, 71.2, "Gujarat"), (21.1, 79.1, "Maharashtra"),
    (30.9, 75.9, "Haryana"), (17.0, 82.0, "Andhra Pradesh"),
]


class RealFacilityFinder:
    """Finds real health facilities from pre-fetched data.gov.in data + Google Maps geocoding."""

    def __init__(self, google_maps_key: str = "", data_gov_key: str = ""):
        self._google_maps_key = google_maps_key
        self._data_gov_key = data_gov_key
        self._facilities: dict[str, list[dict]] = {}
        self._geocode_cache: dict[str, tuple] = {}
        self._loaded = False

    def load(self, path: str) -> None:
        """Load pre-fetched facility data from JSON file."""
        p = Path(path)
        if p.exists():
            with open(p) as f:
                self._facilities = json.load(f)
            total = sum(len(v) for v in self._facilities.values())
            logger.info(f"Loaded {total} real facilities across "
                        f"{len(self._facilities)} states from {p.name}")
            self._loaded = True
        else:
            logger.warning(f"Real facility data not found at {path}")

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    def _guess_state(self, lat: float, lon: float) -> str:
        best_dist = float('inf')
        best_state = "Uttar Pradesh"
        for s_lat, s_lon, state in INDIAN_STATES:
            d = self._haversine(lat, lon, s_lat, s_lon)
            if d < best_dist:
                best_dist = d
                best_state = state
        return best_state

    @staticmethod
    def _make_navigation_url(name: str, address: str, pincode: str,
                              lat: float = None, lon: float = None) -> str:
        if lat and lon:
            return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
        query = f"{name}, {address}" if address else name
        if pincode:
            query += f", {pincode}"
        query += ", India"
        return f"https://www.google.com/maps/dir/?api=1&destination={urllib.parse.quote(query)}"

    async def _geocode_batch(self, facilities: list[dict], state: str,
                              max_count: int = 20) -> int:
        """Geocode facilities missing coordinates using Google Maps API."""
        if not self._google_maps_key:
            return 0

        geocoded = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for f in facilities:
                if f.get("latitude") or geocoded >= max_count:
                    continue
                query = f["name"]
                if f.get("address"):
                    query += f", {f['address']}"
                if f.get("district"):
                    query += f", {f['district']}"
                query += f", {state}, India"
                if f.get("pincode"):
                    query += f" {f['pincode']}"

                cache_key = query.lower().strip()
                if cache_key in self._geocode_cache:
                    lat, lon = self._geocode_cache[cache_key]
                    if lat:
                        f["latitude"] = lat
                        f["longitude"] = lon
                        geocoded += 1
                    continue

                try:
                    resp = await client.get(GOOGLE_GEOCODE_URL, params={
                        "address": query,
                        "key": self._google_maps_key,
                        "region": "in",
                    })
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "OK" and data.get("results"):
                            loc = data["results"][0]["geometry"]["location"]
                            f["latitude"] = loc["lat"]
                            f["longitude"] = loc["lng"]
                            self._geocode_cache[cache_key] = (loc["lat"], loc["lng"])
                            geocoded += 1
                        else:
                            self._geocode_cache[cache_key] = (None, None)
                except Exception as e:
                    logger.debug(f"Geocode failed for '{query}': {e}")

        return geocoded

    async def find_nearby(self, lat: float, lon: float,
                           radius_km: float = 50.0) -> list[dict]:
        """Find nearby real facilities sorted by distance. Includes PHCs, CHCs, hospitals."""
        state = self._guess_state(lat, lon)
        raw_facilities = self._facilities.get(state, [])

        if not raw_facilities:
            logger.warning(f"No facility data for state: {state}")
            return []

        # Build working copies with navigation URLs
        facilities = []
        for f in raw_facilities:
            fc = {**f, "state": state, "source": "data.gov.in"}
            fc["navigation_url"] = self._make_navigation_url(
                fc["name"], fc.get("address", ""),
                fc.get("pincode", ""),
                fc.get("latitude"), fc.get("longitude"))
            facilities.append(fc)

        # Geocode missing coordinates (up to 20 per request to stay in free tier)
        geocoded = await self._geocode_batch(facilities, state, max_count=20)
        if geocoded > 0:
            # Update navigation URLs with new coordinates
            for f in facilities:
                if f.get("latitude"):
                    f["navigation_url"] = self._make_navigation_url(
                        f["name"], f.get("address", ""),
                        f.get("pincode", ""),
                        f["latitude"], f["longitude"])
            logger.info(f"Geocoded {geocoded} facilities in {state}")

        # Compute distances and filter
        results = []
        for f in facilities:
            if f.get("latitude") and f.get("longitude"):
                dist = self._haversine(lat, lon, f["latitude"], f["longitude"])
                f_copy = {**f, "distance_km": round(dist, 1),
                          "has_exact_location": True}
            else:
                f_copy = {**f, "distance_km": None,
                          "has_exact_location": False}

            if f_copy["distance_km"] is None or f_copy["distance_km"] <= radius_km:
                results.append(f_copy)

        exact = sorted(
            [r for r in results if r["has_exact_location"]],
            key=lambda x: x["distance_km"])
        inexact = sorted(
            [r for r in results if not r["has_exact_location"]],
            key=lambda x: x["name"])

        return exact + inexact[:30]

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def total_facilities(self) -> int:
        return sum(len(v) for v in self._facilities.values())
