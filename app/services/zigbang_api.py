"""직방 비공식 API 연동 서비스.

주의: 비공식 API이므로 예고 없이 변경·차단될 수 있습니다.
직방의 sales_type_in 파라미터는 실제로 무시되므로 상세 조회 후 필터링 필요.
아파트는 별도 분양 시스템만 제공되어 개별 매물 목록이 제한적.

검증된 엔드포인트 (2026-02):
- 검색: GET /v2/search?q={keyword}
- 원룸 목록: GET /v2/items/oneroom?geohash={hash}&...
- 오피스텔 목록: GET /v2/items/officetel?geohash={hash}&...
- 빌라 목록: GET /v2/items/villa?geohash={hash}&...
- 상세: GET /v3/items/{item_id}
"""

import asyncio
import logging
from dataclasses import dataclass

import geohash2
import httpx

logger = logging.getLogger(__name__)

BASE = "https://apis.zigbang.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.zigbang.com",
    "Referer": "https://www.zigbang.com/",
}

GEOHASH_ENDPOINTS: dict[str, str] = {
    "원룸": "/v2/items/oneroom",
    "오피스텔": "/v2/items/officetel",
    "빌라": "/v2/items/villa",
}

SALES_TYPE_NORMALIZE: dict[str, str] = {
    "전세": "전세",
    "월세": "월세",
    "매매": "매매",
}


@dataclass
class ZigbangListing:
    item_id: int = 0
    sales_type: str = ""
    service_type: str = ""
    deposit: int = 0
    rent: int = 0
    area_m2: float = 0
    floor: str = ""
    address: str = ""
    title: str = ""
    description: str = ""
    image_url: str = ""
    manage_cost: str = ""


@dataclass
class ZigbangSearchResult:
    name: str = ""
    lat: float = 0
    lng: float = 0
    id: str = ""
    type: str = ""


class ZigbangAPIService:

    async def search_region(self, keyword: str) -> list[ZigbangSearchResult]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE}/v2/search",
                    params={"leaseYn": "N", "q": keyword},
                    headers=HEADERS,
                )
                resp.raise_for_status()
                data = resp.json()

            results: list[ZigbangSearchResult] = []
            for item in data.get("items", []):
                if item.get("lat") and item.get("lng"):
                    results.append(ZigbangSearchResult(
                        name=item.get("description", item.get("name", "")),
                        lat=float(item["lat"]),
                        lng=float(item["lng"]),
                        id=str(item.get("id", "")),
                        type=item.get("_type", ""),
                    ))
            return results[:10]
        except Exception as e:
            logger.warning("Zigbang search failed: %s", e)
            return []

    async def get_listings(
        self,
        lat: float,
        lng: float,
        sales_type: str = "전세",
        service_type: str = "원룸",
    ) -> list[ZigbangListing]:
        ghash = geohash2.encode(lat, lng, precision=5)

        if service_type == "아파트":
            item_ids = await self._fetch_all_item_ids(ghash)
        else:
            item_ids = await self._fetch_item_ids(ghash, service_type)
            if not item_ids:
                for dlat in (0.005, -0.005):
                    for dlng in (0.005, -0.005):
                        adj = geohash2.encode(lat + dlat, lng + dlng, precision=5)
                        if adj != ghash:
                            item_ids = await self._fetch_item_ids(adj, service_type)
                            if item_ids:
                                break
                    if item_ids:
                        break

        if not item_ids:
            return []

        batch = item_ids[:50]
        tasks = [self._fetch_single_detail(iid) for iid in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        target_sales = SALES_TYPE_NORMALIZE.get(sales_type, "")
        listings: list[ZigbangListing] = []
        for r in results:
            if not isinstance(r, ZigbangListing) or not r.item_id:
                continue
            if target_sales and r.sales_type and r.sales_type != target_sales:
                continue
            listings.append(r)

        return listings

    async def get_listing_detail(self, item_id: int) -> ZigbangListing | None:
        return await self._fetch_single_detail(item_id)

    async def _fetch_all_item_ids(self, ghash: str) -> list[int]:
        """Fetch IDs from ALL endpoints combined (for apartment search fallback)."""
        tasks = [
            self._fetch_item_ids(ghash, stype)
            for stype in GEOHASH_ENDPOINTS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_ids: list[int] = []
        seen: set[int] = set()
        for r in results:
            if isinstance(r, list):
                for iid in r:
                    if iid not in seen:
                        seen.add(iid)
                        all_ids.append(iid)
        return all_ids[:50]

    async def _fetch_item_ids(
        self, ghash: str, service_type: str,
    ) -> list[int]:
        endpoint = GEOHASH_ENDPOINTS.get(service_type, GEOHASH_ENDPOINTS["원룸"])
        params: dict = {
            "geohash": ghash,
            "deposit_gteq": 0,
            "rent_gteq": 0,
            "domain": "zigbang",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE}{endpoint}",
                    params=params,
                    headers=HEADERS,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            items = data.get("items", [])
            if isinstance(items, list):
                return [
                    int(it.get("itemId") or it.get("item_id") or 0)
                    for it in items
                    if it.get("itemId") or it.get("item_id")
                ][:50]
            return []
        except Exception as e:
            logger.debug("Zigbang IDs fetch failed (gh=%s): %s", ghash, e)
            return []

    async def _fetch_single_detail(self, item_id: int) -> ZigbangListing | None:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(
                    f"{BASE}/v3/items/{item_id}",
                    headers=HEADERS,
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()

            item = data.get("item", data)
            if not isinstance(item, dict):
                return None

            price = item.get("price", {})
            area = item.get("area", {})
            floor_info = item.get("floor", {})
            addr_origin = item.get("addressOrigin", {})

            deposit = _int(price.get("deposit", 0))
            rent = _int(price.get("rent", 0))

            address = item.get("jibunAddress", "")
            if addr_origin and addr_origin.get("fullText"):
                address = addr_origin["fullText"]

            floor_str = ""
            if isinstance(floor_info, dict):
                f = floor_info.get("floor", "")
                af = floor_info.get("allFloors", "")
                floor_str = f"{f}/{af}" if f and af else str(f)
            elif floor_info:
                floor_str = str(floor_info)

            img = item.get("imageThumbnail", "")

            mc = item.get("manageCost", {})
            manage_str = ""
            if isinstance(mc, dict) and mc.get("amount"):
                manage_str = f"{mc['amount']}만원"

            return ZigbangListing(
                item_id=_int(item.get("itemId", item_id)),
                sales_type=item.get("salesType", item.get("sales_type", "")),
                service_type=item.get("serviceType", item.get("service_type", "")),
                deposit=deposit,
                rent=rent,
                area_m2=_float(area.get("전용면적M2") or area.get("전용면적_m2") or 0),
                floor=floor_str,
                address=address,
                title=item.get("title", ""),
                description=item.get("description", ""),
                image_url=img,
                manage_cost=manage_str,
            )
        except Exception as e:
            logger.debug("Zigbang detail %s failed: %s", item_id, e)
            return None


def _int(v) -> int:
    try:
        return int(v) if v else 0
    except (ValueError, TypeError):
        return 0


def _float(v) -> float:
    try:
        return float(v) if v else 0.0
    except (ValueError, TypeError):
        return 0.0
