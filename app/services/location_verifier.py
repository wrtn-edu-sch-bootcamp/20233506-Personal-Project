import asyncio
import logging
import math
import re

from app.models.schemas import (
    LocationClaim,
    LocationVerification,
    NearbyFacilities,
    NearbyFacility,
)
from app.services.kakao_map_service import KakaoMapService

logger = logging.getLogger(__name__)

WALK_SPEED_M_PER_MIN = 67
WALK_DETOUR_FACTOR = 1.3

CATEGORY_SEARCH = {
    "지하철": ("SW8", 1500),
    "지하철역": ("SW8", 1500),
    "역세권": ("SW8", 1500),
    "대형마트": ("MT1", 1500),
    "마트": ("MT1", 1500),
    "편의점": ("CS2", 500),
    "병원": ("HP8", 1500),
    "약국": ("PM9", 1000),
    "은행": ("BK9", 1500),
}

KEYWORD_SEARCH = {
    "초등학교": ("초등학교", 1500),
    "중학교": ("중학교", 1500),
    "고등학교": ("고등학교", 1500),
    "학교": ("초등학교", 1500),
    "학세권": ("초등학교", 1500),
    "유치원": ("유치원", 1000),
    "어린이집": ("어린이집", 1000),
    "공원": ("공원", 1500),
    "놀이터": ("놀이터", 1000),
    "버스": ("버스정류장", 1000),
    "버스정류장": ("버스정류장", 1000),
    "스타벅스": ("스타벅스", 1000),
    "카페": ("카페", 500),
}

CLAIM_PATTERNS = [
    (re.compile(r"도보\s*(\d+)\s*분.*?(지하철|역|학교|초등학교|마트|공원|병원|버스|편의점|은행)", re.IGNORECASE), True),
    (re.compile(r"(지하철|역|학교|초등학교|마트|공원|병원|버스|편의점|은행).*?도보\s*(\d+)\s*분", re.IGNORECASE), True),
    (re.compile(r"(역세권|학세권|초역세권|더블역세권|트리플역세권)", re.IGNORECASE), False),
    (re.compile(r"(초등학교|중학교|고등학교|유치원|어린이집|학교)\s*.{0,4}(근처|인접|앞|가까|도보권|바로|옆)", re.IGNORECASE), False),
    (re.compile(r"(공원|놀이터)\s*.{0,4}(근처|인접|앞|가까|도보권|바로|옆)", re.IGNORECASE), False),
    (re.compile(r"(대형마트|마트|편의점|병원|약국|은행)\s*.{0,4}(근처|인접|앞|가까|도보권|바로|옆)", re.IGNORECASE), False),
    (re.compile(r"(지하철|역)\s*.{0,4}(근처|인접|앞|가까|도보권|바로|옆)", re.IGNORECASE), False),
    (re.compile(r"(버스|버스정류장)\s*.{0,4}(근처|인접|앞|가까|도보권|바로|옆)", re.IGNORECASE), False),
]

FACILITY_ALIASES = {
    "역": "지하철역",
    "지하철": "지하철역",
    "역세권": "지하철역",
    "초역세권": "지하철역",
    "더블역세권": "지하철역",
    "트리플역세권": "지하철역",
    "학세권": "초등학교",
    "학교": "초등학교",
    "마트": "대형마트",
    "대형마트": "대형마트",
    "버스": "버스정류장",
    "버스정류장": "버스정류장",
}


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in meters between two coords."""
    R = 6371000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _walk_minutes(distance_m: float) -> int:
    return max(1, round(distance_m * WALK_DETOUR_FACTOR / WALK_SPEED_M_PER_MIN))


def _parse_claims(location_claims: list[str], listing_text: str) -> list[dict]:
    """Parse location claims into searchable items."""
    parsed: list[dict] = []
    seen_categories: set[str] = set()
    combined = " ".join(location_claims) + " " + listing_text

    for pattern, has_time in CLAIM_PATTERNS:
        for m in pattern.finditer(combined):
            full_match = m.group(0)
            claimed_min = None
            facility_raw = ""

            if has_time:
                groups = m.groups()
                if groups[0].isdigit():
                    claimed_min = int(groups[0])
                    facility_raw = groups[1]
                else:
                    facility_raw = groups[0]
                    if len(groups) > 1 and groups[1].isdigit():
                        claimed_min = int(groups[1])
            else:
                facility_raw = m.group(1)

            category = FACILITY_ALIASES.get(facility_raw, facility_raw)
            if category in seen_categories:
                continue
            seen_categories.add(category)

            parsed.append({
                "claim": full_match.strip(),
                "category": category,
                "claimed_walk_min": claimed_min,
                "facility_raw": facility_raw,
            })

    return parsed


class LocationVerifier:
    def __init__(self, kakao: KakaoMapService) -> None:
        self._kakao = kakao

    async def verify(
        self,
        lat: float,
        lng: float,
        location_claims: list[str],
        listing_text: str = "",
    ) -> LocationVerification:
        if not lat or not lng:
            return LocationVerification()

        parsed = _parse_claims(location_claims, listing_text)
        if not parsed:
            return LocationVerification()

        tasks = [self._verify_single(lat, lng, p) for p in parsed]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        claims: list[LocationClaim] = []
        for r in results:
            if isinstance(r, LocationClaim):
                claims.append(r)

        verified = sum(1 for c in claims if c.verified)
        exaggerated = sum(1 for c in claims if c.verdict == "과장됨")

        return LocationVerification(
            claims=claims,
            verified_count=verified,
            exaggerated_count=exaggerated,
        )

    async def _verify_single(self, lat: float, lng: float, parsed: dict) -> LocationClaim:
        category = parsed["category"]
        claimed_min = parsed["claimed_walk_min"]

        places = await self._search_places(category, lng, lat)

        if not places:
            return LocationClaim(
                claim=parsed["claim"],
                category=category,
                verified=False,
                claimed_walk_min=claimed_min,
                verdict="확인 불가",
            )

        nearest = places[0]
        place_lat = float(nearest.get("y", 0))
        place_lng = float(nearest.get("x", 0))
        place_name = nearest.get("place_name", "")

        dist = nearest.get("distance")
        if dist:
            distance_m = int(dist)
        else:
            distance_m = round(_haversine(lat, lng, place_lat, place_lng))

        walk_min = _walk_minutes(distance_m)

        verified, verdict = self._judge(category, distance_m, walk_min, claimed_min)

        return LocationClaim(
            claim=parsed["claim"],
            category=category,
            verified=verified,
            nearest_name=place_name,
            actual_distance_m=distance_m,
            actual_walk_min=walk_min,
            claimed_walk_min=claimed_min,
            verdict=verdict,
        )

    async def _search_places(self, category: str, lng: float, lat: float) -> list[dict]:
        for key, (code, radius) in CATEGORY_SEARCH.items():
            if key in category or category in key:
                return await self._kakao.search_category(code, lng, lat, radius=radius)

        for key, (keyword, radius) in KEYWORD_SEARCH.items():
            if key in category or category in key:
                return await self._kakao.search_keyword_nearby(keyword, lng, lat, radius=radius)

        return await self._kakao.search_keyword_nearby(category, lng, lat, radius=1500)

    async def search_nearby(
        self,
        lat: float,
        lng: float,
        radius: int = 1000,
    ) -> NearbyFacilities:
        """Search common amenity categories around the given coordinate."""
        if not lat or not lng:
            return NearbyFacilities()

        SEARCHES: list[tuple[str, str, str, int]] = [
            # (field_name, search_type, code_or_keyword, search_radius)
            ("subway", "category", "SW8", 1500),
            ("school", "keyword", "학교", radius),
            ("mart", "category", "MT1", radius),
            ("hospital", "category", "HP8", radius),
            ("park", "keyword", "공원", radius),
            ("convenience", "category", "CS2", 500),
            ("cafe", "category", "CE7", 500),
            ("bank", "category", "BK9", radius),
        ]

        async def _do_search(
            field: str, stype: str, code_or_kw: str, r: int
        ) -> tuple[str, list[dict]]:
            if stype == "category":
                results = await self._kakao.search_category(code_or_kw, lng, lat, radius=r, size=3)
            else:
                results = await self._kakao.search_keyword_nearby(code_or_kw, lng, lat, radius=r, size=3)
            return field, results

        tasks = [_do_search(f, st, ck, sr) for f, st, ck, sr in SEARCHES]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        data: dict[str, list[NearbyFacility]] = {}
        for result in raw_results:
            if isinstance(result, Exception):
                continue
            field, places = result
            items: list[NearbyFacility] = []
            for p in places:
                dist = int(p.get("distance", 0)) if p.get("distance") else round(
                    _haversine(lat, lng, float(p.get("y", 0)), float(p.get("x", 0)))
                )
                items.append(NearbyFacility(
                    name=p.get("place_name", ""),
                    category=p.get("category_name", "").split(" > ")[-1] if p.get("category_name") else field,
                    distance_m=dist,
                    walk_min=_walk_minutes(dist),
                ))
            data[field] = items

        return NearbyFacilities(**data)

    @staticmethod
    def _judge(
        category: str,
        distance_m: int,
        walk_min: int,
        claimed_min: int | None,
    ) -> tuple[bool, str]:
        if claimed_min is not None:
            if walk_min <= claimed_min * 1.5:
                return True, "확인됨"
            else:
                return False, "과장됨"

        if "지하철" in category or "역" in category:
            if distance_m <= 500:
                return True, "확인됨"
            elif distance_m <= 1000:
                return False, "과장됨"
            else:
                return False, "과장됨"
        else:
            if distance_m <= 800:
                return True, "확인됨"
            elif distance_m <= 1500:
                return False, "과장됨"
            else:
                return False, "과장됨"
