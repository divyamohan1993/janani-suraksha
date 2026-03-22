"""Real facility finder using Google Places API for accurate nearby hospitals."""
import json
import math
import logging
from pathlib import Path
import urllib.parse
import httpx

logger = logging.getLogger("janani.facilities")

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


class RealFacilityFinder:
    """Finds real nearby health facilities using Google Places API.

    Primary: Google Places Nearby Search (accurate coordinates, real-time)
    Fallback: Pre-fetched data.gov.in data (offline, broader coverage)
    """

    def __init__(self, google_maps_key: str = "", data_gov_key: str = ""):
        self._google_maps_key = google_maps_key
        self._data_gov_key = data_gov_key
        self._datagov_facilities: dict[str, list[dict]] = {}
        self._places_cache: dict[str, list[dict]] = {}
        self._loaded = False

    def load(self, path: str) -> None:
        """Load pre-fetched data.gov.in facility data as fallback."""
        p = Path(path)
        if p.exists():
            with open(p) as f:
                self._datagov_facilities = json.load(f)
            total = sum(len(v) for v in self._datagov_facilities.values())
            logger.info(f"Loaded {total} data.gov.in facilities across "
                        f"{len(self._datagov_facilities)} states (fallback)")
            self._loaded = True

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    async def _search_google_places(self, lat: float, lon: float,
                                      radius_m: int = 25000) -> list[dict]:
        cache_key = f"{lat:.2f},{lon:.2f},{radius_m}"
        if cache_key in self._places_cache:
            return self._places_cache[cache_key]

        if not self._google_maps_key:
            return []

        facilities = []
        searches = [
            {"type": "hospital", "keyword": "maternity hospital district hospital"},
            {"type": "hospital", "keyword": ""},
            {"keyword": "PHC primary health centre CHC community health centre"},
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for search in searches:
                try:
                    params = {
                        "location": f"{lat},{lon}",
                        "radius": radius_m,
                        "key": self._google_maps_key,
                    }
                    if search.get("type"):
                        params["type"] = search["type"]
                    if search.get("keyword"):
                        params["keyword"] = search["keyword"]

                    resp = await client.get(PLACES_NEARBY_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "OK":
                            for place in data.get("results", []):
                                loc = place["geometry"]["location"]
                                dist = self._haversine(lat, lon, loc["lat"], loc["lng"])
                                name_lower = place["name"].lower()
                                types = place.get("types", [])
                                rating = place.get("rating")
                                reviews = place.get("user_ratings_total", 0)

                                # FILTER: skip if not a real hospital
                                # Must have "hospital" in types OR "hospital/nursing/clinic" in name
                                is_hospital = (
                                    "hospital" in types or
                                    any(kw in name_lower for kw in [
                                        "hospital", "nursing home", "clinic",
                                        "medical", "health centre", "health center",
                                        "phc", "chc", "dispensary", "maternity",
                                    ])
                                )
                                if not is_hospital:
                                    continue

                                # FILTER: skip listings with no reviews and no rating
                                # (likely spam/fake entries)
                                if rating is None and reviews == 0:
                                    continue

                                # Compute maternity relevance score
                                maternity_score = 0
                                if any(kw in name_lower for kw in ["maternity", "obstetric", "gynae", "women", "mahila", "janani", "mother", "prasuti"]):
                                    maternity_score = 3
                                elif any(kw in name_lower for kw in ["district hospital", "civil hospital", "government hospital", "zonal hospital"]):
                                    maternity_score = 2
                                elif "hospital" in types or "hospital" in name_lower:
                                    maternity_score = 1

                                facilities.append({
                                    "name": place["name"],
                                    "category": ", ".join(
                                        t.replace("_", " ").title()
                                        for t in types[:2]
                                        if t not in ("point_of_interest", "establishment")
                                    ) or "Hospital",
                                    "address": place.get("vicinity", ""),
                                    "district": "",
                                    "state": "",
                                    "pincode": "",
                                    "phone": "",
                                    "rating": place.get("rating"),
                                    "reviews": place.get("user_ratings_total", 0),
                                    "open_now": place.get("opening_hours", {}).get("open_now"),
                                    "latitude": loc["lat"],
                                    "longitude": loc["lng"],
                                    "distance_km": round(dist, 1),
                                    "has_exact_location": True,
                                    "maternity_score": maternity_score,
                                    "navigation_url": (
                                        f"https://www.google.com/maps/dir/?api=1"
                                        f"&destination={loc['lat']},{loc['lng']}"
                                        f"&destination_place_id={place.get('place_id', '')}"
                                    ),
                                    "source": "google_places",
                                })
                except Exception as e:
                    logger.warning(f"Google Places search failed: {e}")

        # Deduplicate
        seen = set()
        unique = []
        for f in facilities:
            key = f["name"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(f)

        # Sort: maternity relevance first, then distance
        unique.sort(key=lambda x: (-x.get("maternity_score", 0), x["distance_km"]))

        self._places_cache[cache_key] = unique[:5]
        logger.info(f"Google Places: found {len(unique)} facilities, returning top 5 near {lat:.4f},{lon:.4f}")
        return unique[:5]

    async def find_nearby(self, lat: float, lon: float,
                           radius_km: float = 25.0) -> list[dict]:
        """Find nearby real facilities. Uses Google Places API with data.gov.in fallback."""
        radius_m = int(min(radius_km, 50) * 1000)  # Cap at 50km for Places API

        # Primary: Google Places API (accurate, real-time)
        facilities = await self._search_google_places(lat, lon, radius_m)

        if facilities:
            return facilities[:5]

        # Fallback: data.gov.in pre-fetched data
        logger.info("Google Places returned no results, falling back to data.gov.in")
        return self._fallback_datagov(lat, lon, radius_km)

    def _fallback_datagov(self, lat: float, lon: float,
                           radius_km: float) -> list[dict]:
        """Fallback to data.gov.in when Google Places is unavailable."""
        state = self._guess_state(lat, lon)
        raw = self._datagov_facilities.get(state, [])
        if not raw:
            return []

        results = []
        for f in raw:
            nav_parts = [f["name"]]
            if f.get("address"):
                nav_parts.append(f["address"])
            if f.get("district"):
                nav_parts.append(f["district"])
            nav_parts.append(state)
            nav_parts.append("India")
            query = ", ".join(nav_parts)

            results.append({
                **f,
                "state": state,
                "source": "data.gov.in",
                "distance_km": None,
                "has_exact_location": False,
                "navigation_url": f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}",
            })

        return results[:30]

    def _guess_state(self, lat: float, lon: float) -> str:
        # All 28 states + 8 Union Territories with real capital coordinates
        states = [
            # 28 States
            (16.5062, 80.6480, "Andhra Pradesh"),
            (27.0844, 93.6053, "Arunachal Pradesh"),
            (26.1433, 91.7898, "Assam"),
            (25.6093, 85.1376, "Bihar"),
            (21.2514, 81.6296, "Chhattisgarh"),
            (15.4909, 73.8278, "Goa"),
            (23.2156, 72.6369, "Gujarat"),
            (30.7333, 76.7794, "Haryana"),
            (31.1048, 77.1734, "Himachal Pradesh"),
            (23.3441, 85.3096, "Jharkhand"),
            (12.9716, 77.5946, "Karnataka"),
            (8.5241, 76.9366, "Kerala"),
            (23.2599, 77.4126, "Madhya Pradesh"),
            (19.0760, 72.8777, "Maharashtra"),
            (24.8170, 93.9368, "Manipur"),
            (25.5788, 91.8933, "Meghalaya"),
            (23.7271, 92.7176, "Mizoram"),
            (25.6751, 94.1086, "Nagaland"),
            (20.2961, 85.8245, "Odisha"),
            (30.7333, 76.7794, "Punjab"),
            (26.9124, 75.7873, "Rajasthan"),
            (27.3389, 88.6065, "Sikkim"),
            (13.0827, 80.2707, "Tamil Nadu"),
            (17.3850, 78.4867, "Telangana"),
            (23.8315, 91.2868, "Tripura"),
            (26.8467, 80.9462, "Uttar Pradesh"),
            (30.3165, 78.0322, "Uttarakhand"),
            (22.5726, 88.3639, "West Bengal"),
            # 8 Union Territories
            (11.6234, 92.7265, "Andaman and Nicobar Islands"),
            (30.7333, 76.7794, "Chandigarh"),
            (20.3974, 72.8328, "Dadra and Nagar Haveli and Daman and Diu"),
            (28.6139, 77.2090, "Delhi"),
            (34.0837, 74.7973, "Jammu and Kashmir"),
            (34.1526, 77.5771, "Ladakh"),
            (10.5593, 72.6358, "Lakshadweep"),
            (11.9416, 79.8083, "Puducherry"),
        ]
        best_dist = float('inf')
        best_state = ""
        for s_lat, s_lon, state in states:
            d = self._haversine(lat, lon, s_lat, s_lon)
            if d < best_dist:
                best_dist = d
                best_state = state
        return best_state

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def total_facilities(self) -> int:
        return sum(len(v) for v in self._datagov_facilities.values())
