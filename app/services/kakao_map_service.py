import logging
import re
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

KAKAO_LOCAL_URL = "https://dapi.kakao.com/v2/local"

def _strip_detail_address(address: str) -> str:
    """Remove apartment unit details (동/호/층) that break geocoding.

    Preserves the road name + building number (e.g. '솔안밀길 21') but strips
    unit-level details like '107동 602호', '501호', '3층'.
    """
    base = address.strip()

    # "107동 602호" or "107동602호"
    base = re.sub(r"\s+\d{1,4}동\s*\d{1,4}호", "", base)
    # standalone "XXX동" (apartment building number, not 법정동)
    base = re.sub(r"\s+\d{1,4}동(?=\s|$)", "", base)
    # standalone "XXX호"
    base = re.sub(r"\s+\d{1,4}호(?=\s|$)", "", base)
    # "제X층" or "X층"
    base = re.sub(r"\s+제?\d{1,3}층(?=\s|$)", "", base)
    # trailing "XXX-XXX" unit pattern (e.g. "21 107-602" → keep "21")
    base = re.sub(r"\s+\d{1,4}-\d{1,4}$", "", base)
    # trailing parenthesized content like "(솔안아파트)"
    base = re.sub(r"\s*\(.*?\)\s*$", "", base)

    base = base.strip()
    return base if len(base) >= 5 else address


@dataclass
class GeocodingResult:
    address: str
    lat: float
    lng: float
    region_code: str  # 법정동 코드 10자리
    lawd_cd: str      # 국토교통부 API용 5자리 코드 (시군구)
    bjdong_cd: str = ""  # 법정동 코드 뒤 5자리
    main_no: str = ""    # 지번 본번
    sub_no: str = ""     # 지번 부번
    region_1depth: str = ""  # 시/도
    region_2depth: str = ""  # 시/군/구
    region_3depth: str = ""  # 읍/면/동


class KakaoMapService:
    """카카오맵 REST API를 사용한 지오코딩 서비스."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.kakao_api_key
        self._headers = {"Authorization": f"KakaoAK {self._api_key}"}

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def geocode(self, address: str) -> GeocodingResult | None:
        """주소 텍스트 → 좌표 + 법정동 코드 변환."""
        if not self.is_available:
            logger.warning("Kakao API key not configured, falling back to keyword parsing")
            return self._fallback_geocode(address)

        clean = _strip_detail_address(address)
        if clean != address:
            logger.info("Geocode: stripped detail '%s' → '%s'", address, clean)

        try:
            result = await self._search_address(clean)
            if result:
                return result
        except Exception as e:
            logger.warning("Kakao address search failed: %s", e)

        if clean != address:
            try:
                result = await self._search_address(address)
                if result:
                    return result
            except Exception:
                pass

        try:
            return await self._search_keyword(clean)
        except Exception as e2:
            logger.warning("Kakao keyword search also failed: %s", e2)
            return self._fallback_geocode(address)

    async def _search_address(self, address: str) -> GeocodingResult | None:
        """카카오 주소 검색 API — 정확한 주소 입력에 적합."""
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{KAKAO_LOCAL_URL}/search/address.json",
                headers=self._headers,
                params={"query": address, "analyze_type": "similar"},
            )
            resp.raise_for_status()
            data = resp.json()

        documents = data.get("documents", [])
        if not documents:
            return None

        doc = documents[0]
        b_code = ""
        region_1 = ""
        region_2 = ""
        region_3 = ""
        main_no = ""
        sub_no = ""

        if doc.get("address"):
            addr = doc["address"]
            b_code = addr.get("b_code", "")
            region_1 = addr.get("region_1depth_name", "")
            region_2 = addr.get("region_2depth_name", "")
            region_3 = addr.get("region_3depth_name", "")
            main_no = addr.get("main_address_no", "")
            sub_no = addr.get("sub_address_no", "")
        elif doc.get("road_address"):
            road = doc["road_address"]
            b_code = road.get("zone_no", "")
            region_1 = road.get("region_1depth_name", "")
            region_2 = road.get("region_2depth_name", "")
            region_3 = road.get("region_3depth_name", "")
            if doc.get("address"):
                main_no = doc["address"].get("main_address_no", "")
                sub_no = doc["address"].get("sub_address_no", "")

        if not b_code and doc.get("x") and doc.get("y"):
            region = await self._coord_to_region(float(doc["x"]), float(doc["y"]))
            if region:
                b_code = region.get("code", "")
                region_1 = region.get("region_1depth_name", region_1)
                region_2 = region.get("region_2depth_name", region_2)
                region_3 = region.get("region_3depth_name", region_3)

        bjdong = b_code[5:] if len(b_code) >= 10 else ""

        return GeocodingResult(
            address=doc.get("address_name", address),
            lat=float(doc.get("y", 0)),
            lng=float(doc.get("x", 0)),
            region_code=b_code,
            lawd_cd=b_code[:5] if len(b_code) >= 5 else "",
            bjdong_cd=bjdong,
            main_no=main_no,
            sub_no=sub_no,
            region_1depth=region_1,
            region_2depth=region_2,
            region_3depth=region_3,
        )

    async def _search_keyword(self, query: str) -> GeocodingResult | None:
        """카카오 키워드 검색 API — 장소명/대략적인 주소에 적합."""
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{KAKAO_LOCAL_URL}/search/keyword.json",
                headers=self._headers,
                params={"query": query},
            )
            resp.raise_for_status()
            data = resp.json()

        documents = data.get("documents", [])
        if not documents:
            return None

        doc = documents[0]
        lng, lat = float(doc.get("x", 0)), float(doc.get("y", 0))

        region = await self._coord_to_region(lng, lat) if lng and lat else None
        b_code = region.get("code", "") if region else ""

        return GeocodingResult(
            address=doc.get("address_name", query),
            lat=lat,
            lng=lng,
            region_code=b_code,
            lawd_cd=b_code[:5] if len(b_code) >= 5 else "",
            region_1depth=region.get("region_1depth_name", "") if region else "",
            region_2depth=region.get("region_2depth_name", "") if region else "",
            region_3depth=region.get("region_3depth_name", "") if region else "",
        )

    async def search_category(
        self,
        category_code: str,
        lng: float,
        lat: float,
        radius: int = 1000,
        size: int = 5,
    ) -> list[dict]:
        """카테고리 코드로 좌표 반경 내 장소 검색. 거리순 정렬."""
        if not self.is_available:
            return []
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{KAKAO_LOCAL_URL}/search/category.json",
                    headers=self._headers,
                    params={
                        "category_group_code": category_code,
                        "x": lng,
                        "y": lat,
                        "radius": radius,
                        "sort": "distance",
                        "size": size,
                    },
                )
                resp.raise_for_status()
                return resp.json().get("documents", [])
        except Exception as e:
            logger.warning("Category search failed (%s): %s", category_code, e)
            return []

    async def search_keyword_nearby(
        self,
        keyword: str,
        lng: float,
        lat: float,
        radius: int = 1000,
        size: int = 5,
    ) -> list[dict]:
        """키워드로 좌표 반경 내 장소 검색. 거리순 정렬."""
        if not self.is_available:
            return []
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{KAKAO_LOCAL_URL}/search/keyword.json",
                    headers=self._headers,
                    params={
                        "query": keyword,
                        "x": lng,
                        "y": lat,
                        "radius": radius,
                        "sort": "distance",
                        "size": size,
                    },
                )
                resp.raise_for_status()
                return resp.json().get("documents", [])
        except Exception as e:
            logger.warning("Keyword nearby search failed (%s): %s", keyword, e)
            return []

    async def reverse_geocode(self, lat: float, lng: float) -> str | None:
        """좌표 → 지번/도로명 주소 변환."""
        if not self.is_available:
            return None
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{KAKAO_LOCAL_URL}/geo/coord2address.json",
                    headers=self._headers,
                    params={"x": lng, "y": lat},
                )
                resp.raise_for_status()
                data = resp.json()

            docs = data.get("documents", [])
            if not docs:
                return None
            doc = docs[0]
            road = doc.get("road_address")
            if road and road.get("address_name"):
                return road["address_name"]
            addr = doc.get("address")
            if addr and addr.get("address_name"):
                return addr["address_name"]
            return None
        except Exception as e:
            logger.warning("Reverse geocode failed: %s", e)
            return None

    async def _coord_to_region(self, lng: float, lat: float) -> dict | None:
        """좌표 → 법정동 정보 변환."""
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{KAKAO_LOCAL_URL}/geo/coord2regioncode.json",
                headers=self._headers,
                params={"x": lng, "y": lat},
            )
            resp.raise_for_status()
            data = resp.json()

        for doc in data.get("documents", []):
            if doc.get("region_type") == "B":  # B = 법정동
                return doc
        return None

    @staticmethod
    def _fallback_geocode(address: str) -> GeocodingResult | None:
        """API 키 없을 때 주소 텍스트에서 구/동 정보를 파싱하여 근사 매칭."""
        KNOWN_DISTRICTS: dict[str, str] = {
            "강남구": "11680", "서초구": "11650", "송파구": "11710",
            "마포구": "11440", "용산구": "11170", "성동구": "11200",
            "영등포구": "11560", "강동구": "11740", "광진구": "11215",
            "동작구": "11590", "관악구": "11620", "종로구": "11110",
            "중구": "11140", "강서구": "11500", "양천구": "11470",
            "구로구": "11530", "노원구": "11350", "도봉구": "11320",
            "성북구": "11290", "강북구": "11305", "은평구": "11380",
            "서대문구": "11410", "중랑구": "11260", "동대문구": "11230",
            "금천구": "11545",
        }

        for district, code in KNOWN_DISTRICTS.items():
            if district in address:
                return GeocodingResult(
                    address=address,
                    lat=0,
                    lng=0,
                    region_code=code + "00000",
                    lawd_cd=code,
                    region_1depth="서울특별시",
                    region_2depth=district,
                    region_3depth="",
                )
        return None


def get_kakao_map_service() -> KakaoMapService:
    return KakaoMapService()
