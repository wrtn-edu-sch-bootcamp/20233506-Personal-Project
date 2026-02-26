import asyncio
import logging
import re
from typing import Any

import httpx

from app.models.schemas import ScrapeListingResponse
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

SCRAPE_PROMPT = """부동산 매물 웹페이지에서 정보를 추출하여 JSON으로 반환하세요.

중요 규칙:
- "address"는 반드시 실제 도로명 또는 지번 주소여야 합니다 (예: "서울시 강남구 삼성로 212", "서울 마포구 성산동 123-4").
- "역세권", "초등학교 근처" 같은 매물 홍보 문구는 절대 address에 넣지 마세요.
- 주소를 찾을 수 없으면 address를 빈 문자열("")로 두세요. 절대 추측하지 마세요.
- "listing_text"에는 매물 설명, 특징, 주변환경 등 모든 서술 텍스트를 넣으세요.
- 텍스트에 없는 정보는 빈 문자열 또는 null로 두세요.

JSON 형식:
{
  "address": "도로명 또는 지번 주소 (없으면 빈 문자열)",
  "building_name": "건물/단지명",
  "deposit": 보증금(만원, 숫자만, 없으면 null),
  "monthly_rent": 월세(만원, 숫자만, 없으면 null),
  "area_sqm": 전용면적(㎡, 숫자만, 없으면 null),
  "floor": "층수 정보",
  "listing_text": "매물 설명 전체",
  "listing_type": "전세 또는 월세 또는 매매",
  "property_type": "아파트 또는 연립다세대 또는 단독다가구 또는 오피스텔"
}
"""

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

API_HEADERS = {
    **BROWSER_HEADERS,
    "Accept": "application/json, text/plain, */*",
}

NAVER_TRADE_TYPE = {"A1": "매매", "B1": "전세", "B2": "월세", "B3": "단기임대"}
NAVER_PROPERTY_TYPE = {
    "APT": "아파트", "ABYG": "아파트", "JGC": "아파트",
    "OFT": "오피스텔", "OPST": "오피스텔",
    "VL": "연립다세대", "DDDGG": "단독다가구",
    "JT": "단독다가구", "SG": "단독다가구",
}


def _detect_source(url: str) -> str:
    if "zigbang" in url or "zigba.ng" in url:
        return "직방"
    if "dabangapp" in url or "다방" in url or "dabang" in url:
        return "다방"
    if ("naver" in url and "land" in url) or "fin.land" in url or "new.land" in url:
        return "네이버부동산"
    if "peter-pan" in url:
        return "피터팬"
    return "기타"


def _extract_naver_article_id(url: str) -> str | None:
    m = re.search(r"/articles?/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]articleId=(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/land/articles?/(\d+)", url)
    if m:
        return m.group(1)
    return None


def _extract_zigbang_ids(url: str) -> dict[str, str]:
    """Extract all possible Zigbang IDs from a URL."""
    ids: dict[str, str] = {}
    m = re.search(r"/items?/(\d+)", url) or re.search(r"item_id=(\d+)", url)
    if m:
        ids["item_id"] = m.group(1)
    m = re.search(r"firstItemId=(\d+)", url)
    if m:
        ids["item_id"] = m.group(1)
    m = re.search(r"areaHoId=(\d+)", url)
    if m:
        ids["area_ho_id"] = m.group(1)
    m = re.search(r"danjis/(\d+)", url)
    if m:
        ids["danji_id"] = m.group(1)
    return ids


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _clean_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:8000]


def _extract_og_meta(html: str) -> dict[str, str]:
    """Extract Open Graph meta tags from HTML."""
    meta: dict[str, str] = {}
    for m in re.finditer(r'<meta\s+(?:property|name)=["\']og:(\w+)["\']\s+content=["\']([^"\']*)["\']', html):
        meta[m.group(1)] = m.group(2)
    for m in re.finditer(r'content=["\']([^"\']*)["\'].*?(?:property|name)=["\']og:(\w+)["\']', html):
        meta[m.group(2)] = m.group(1)
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
    if title_m:
        meta["title"] = title_m.group(1).strip()
    desc_m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', html)
    if desc_m:
        meta["meta_description"] = desc_m.group(1)
    return meta


ADDRESS_MARKERS = re.compile(
    r"(시|군|구|읍|면|동|리|로|길|가|대로)\s|"
    r"\d{1,5}-\d{1,5}|"
    r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
)
PROMO_MARKERS = re.compile(r"(역세권|학세권|근처|인접|가까|리모델링|신축|풀옵션|즉시입주|올수리)")


def _looks_like_address(text: str) -> bool:
    if not text or len(text) < 5:
        return False
    if PROMO_MARKERS.search(text) and not ADDRESS_MARKERS.search(text):
        return False
    if ADDRESS_MARKERS.search(text):
        return True
    return len(text) < 50


def _guess_listing_type(text: str) -> str:
    if "매매" in text:
        return "매매"
    if "월세" in text:
        return "월세"
    if "전세" in text:
        return "전세"
    return ""


def _guess_property_type(text: str) -> str:
    if "아파트" in text:
        return "아파트"
    if "오피스텔" in text:
        return "오피스텔"
    if any(k in text for k in ("빌라", "연립", "다세대")):
        return "연립다세대"
    if any(k in text for k in ("단독", "다가구")):
        return "단독다가구"
    return ""


class ListingScraper:
    def __init__(self) -> None:
        self._llm = LLMService()

    async def scrape(self, url: str) -> ScrapeListingResponse:
        source = _detect_source(url)
        logger.info("Scraping listing from %s: %s", source, url)

        try:
            if source == "네이버부동산":
                return await self._scrape_naver(url)
            if source == "직방":
                return await self._scrape_zigbang(url)
            if source == "다방":
                return await self._scrape_dabang(url)
            return await self._scrape_generic(url, source)
        except Exception as e:
            logger.warning("Scrape failed for %s: %s", source, e)
            return ScrapeListingResponse(
                source=source,
                listing_text=f"매물 정보를 가져오지 못했습니다: {e}",
            )

    # ── 네이버부동산 ──

    async def _scrape_naver(self, url: str) -> ScrapeListingResponse:
        article_id = _extract_naver_article_id(url)
        if not article_id:
            return ScrapeListingResponse(
                source="네이버부동산",
                listing_text="URL에서 매물 ID를 찾을 수 없습니다. 네이버부동산 매물 URL을 확인해주세요.",
            )

        result = await self._try_naver_api(article_id)
        if result:
            return result

        result = await self._try_naver_html(url, article_id)
        if result:
            return result

        return ScrapeListingResponse(
            source="네이버부동산",
            listing_text=(
                f"네이버부동산 매물(ID: {article_id})을 가져올 수 없습니다.\n\n"
                "가능한 원인:\n"
                "• 매물이 삭제되었거나 거래가 완료되었습니다\n"
                "• 비공개 매물이거나 임시 접근 제한 중입니다\n\n"
                "매물이 존재하는 경우, 매물 페이지의 정보를 직접 입력해주세요."
            ),
        )

    async def _try_naver_api(self, article_id: str) -> ScrapeListingResponse | None:
        endpoints = [
            ("https://fin.land.naver.com/front-api/v1/article/basicInfo", "https://fin.land.naver.com/"),
            ("https://new.land.naver.com/api/articles/{id}", "https://new.land.naver.com/"),
        ]

        for base_url, referer in endpoints:
            url = base_url.replace("{id}", article_id)
            params = {"articleId": article_id} if "front-api" in base_url else {}
            headers = {**API_HEADERS, "Referer": referer}

            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                        resp = await client.get(url, params=params, headers=headers)

                    if resp.status_code == 404:
                        logger.info("Naver article %s: 404", article_id)
                        return None

                    if resp.status_code == 429:
                        if attempt == 0:
                            await asyncio.sleep(2)
                            continue
                        logger.info("Naver rate limited persistently")
                        break

                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    if isinstance(data, dict) and (
                        data.get("detailCode") == "TOO_MANY_REQUESTS"
                        or data.get("code") == "TOO_MANY_REQUESTS"
                    ):
                        if attempt == 0:
                            await asyncio.sleep(2)
                            continue
                        break

                    result = data.get("result", data) if isinstance(data, dict) else data
                    if not isinstance(result, dict):
                        break

                    return self._parse_naver_data(result, article_id)

                except Exception as e:
                    logger.debug("Naver API attempt failed: %s", e)
                    break

        return None

    async def _try_naver_html(self, url: str, article_id: str) -> ScrapeListingResponse | None:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers=BROWSER_HEADERS)

            final_url = str(resp.url)
            if "/404" in final_url:
                return None

            if resp.status_code in (404, 410):
                return None

            if resp.status_code != 200:
                return None

            html = resp.text
            meta = _extract_og_meta(html)

            if not meta.get("title") and not meta.get("description"):
                return None

            title = meta.get("title", "")
            if "세상의 모든 지식" in title or "네이버 ::" in title or "네이버페이 부동산" in title:
                return None
            if "집주인이 확인한" in meta.get("description", ""):
                desc_raw = meta.get("description", "")
                if not ADDRESS_MARKERS.search(desc_raw):
                    meta["description"] = ""

            full_text = " ".join(meta.values())
            listing_type = _guess_listing_type(full_text)
            property_type = _guess_property_type(full_text)

            deposit = None
            price_match = re.search(r"(\d[\d,]+)\s*만원", title + " " + meta.get("description", ""))
            if price_match:
                deposit = _safe_int(price_match.group(1).replace(",", ""))

            area = None
            area_match = re.search(r"([\d.]+)\s*㎡", full_text)
            if area_match:
                area = _safe_float(area_match.group(1))

            raw_address = meta.get("description", "")
            address = raw_address if _looks_like_address(raw_address) else ""

            raw_building = title.split(" ")[0] if title else ""
            building_name = ""
            if raw_building and raw_building not in ("네이버", "부동산", "매물"):
                building_name = raw_building

            if not address and not building_name and not deposit:
                return None

            return ScrapeListingResponse(
                address=address,
                building_name=building_name,
                deposit=deposit,
                area_sqm=area,
                listing_text=meta.get("meta_description", title),
                listing_type=listing_type,
                property_type=property_type,
                source="네이버부동산",
            )

        except Exception as e:
            logger.debug("Naver HTML fallback failed: %s", e)
            return None

    def _parse_naver_data(self, data: dict, article_id: str) -> ScrapeListingResponse:
        article = data.get("article", data.get("articleDetail", data))
        if not isinstance(article, dict):
            article = data

        trade_code = article.get("tradeTypeCode", "")
        trade_name = article.get("tradeTypeName", "")
        listing_type = NAVER_TRADE_TYPE.get(trade_code, "") or _guess_listing_type(trade_name) or "전세"

        prop_code = article.get("realEstateTypeCode", "")
        prop_name = article.get("realEstateTypeName", "")
        property_type = NAVER_PROPERTY_TYPE.get(prop_code, "") or _guess_property_type(prop_name) or "아파트"

        deposit = _safe_int(
            article.get("dealOrWarrantPrc")
            or article.get("warrantPrice")
            or article.get("dealPrice")
        )
        monthly = _safe_int(article.get("rentPrc") or article.get("rentPrice"))
        area = _safe_float(article.get("exclusiveArea") or article.get("area2"))
        floor_info = article.get("floorInfo", "") or str(article.get("floor", ""))

        address_parts = [
            article.get("cityName", ""),
            article.get("divisionName", ""),
            article.get("sectionName", ""),
            article.get("streetName", ""),
            article.get("detailAddress", ""),
        ]
        address = " ".join(p for p in address_parts if p).strip()
        if not address:
            address = article.get("exposureAddress", "") or article.get("address", "")

        building = article.get("complexName", "") or article.get("buildingName", "")
        desc = article.get("articleFeatureDescription", "") or article.get("description", "")
        detail_desc = article.get("articleDetailDescription", "") or article.get("detailDescription", "")
        listing_text = f"{desc}\n{detail_desc}".strip() or f"{building} {listing_type} 매물"

        if deposit and deposit < 200:
            deposit = int(deposit * 10000)

        return ScrapeListingResponse(
            address=address,
            building_name=building,
            deposit=deposit,
            monthly_rent=monthly if monthly and monthly > 0 else None,
            area_sqm=area,
            floor=floor_info,
            listing_text=listing_text,
            listing_type=listing_type,
            property_type=property_type,
            source="네이버부동산",
        )

    # ── 직방 ──

    async def _scrape_zigbang(self, url: str) -> ScrapeListingResponse:
        resolved_url = url
        final_html = ""

        resolved_url, final_html = await self._resolve_zigbang_redirect(url)
        if resolved_url != url:
            logger.info("Zigbang link resolved → %s", resolved_url[:120])

        all_ids = _extract_zigbang_ids(url)
        all_ids.update(_extract_zigbang_ids(resolved_url))

        item_id = all_ids.get("item_id")
        if item_id:
            for api_fn in (self._try_zigbang_api_v2, self._try_zigbang_api_v3_list):
                result = await api_fn(item_id)
                if result:
                    return result

        area_ho_id = all_ids.get("area_ho_id")
        danji_id = all_ids.get("danji_id")
        if area_ho_id:
            result = await self._try_zigbang_apt_api(area_ho_id, danji_id)
            if result:
                return result

        target_url = resolved_url if resolved_url != url else url
        result = await self._try_zigbang_html(target_url, existing_html=final_html)
        if result:
            return result

        if final_html:
            result = await self._try_zigbang_og_llm(final_html, resolved_url)
            if result:
                return result

        return ScrapeListingResponse(
            source="직방",
            listing_text=(
                "직방 매물 정보를 자동으로 가져올 수 없습니다.\n\n"
                "직방은 앱/웹에서 JavaScript로 데이터를 로딩하여 자동 추출이 제한됩니다.\n\n"
                "아래 정보를 직방 매물 페이지에서 직접 복사해 입력해주세요:\n"
                "• 주소 (도로명주소)\n"
                "• 매매가/보증금\n"
                "• 전용면적\n"
                "• 매물 설명"
            ),
        )

    async def _resolve_zigbang_redirect(self, url: str) -> tuple[str, str]:
        """Follow redirect chain from zigba.ng short URL and return (final_url, html)."""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=BROWSER_HEADERS)
                return str(resp.url), resp.text if resp.status_code == 200 else ""
        except Exception as e:
            logger.warning("Zigbang redirect resolve failed: %s", e)
            return url, ""

    async def _try_zigbang_apt_api(
        self, area_ho_id: str, danji_id: str | None = None,
    ) -> ScrapeListingResponse | None:
        """Try Zigbang apartment-specific API endpoints."""
        endpoints = [
            f"https://apis.zigbang.com/v3/items/area-ho/{area_ho_id}",
            f"https://apis.zigbang.com/v2/items/area-ho/{area_ho_id}",
        ]
        if danji_id:
            endpoints.append(
                f"https://apis.zigbang.com/apt/danjis/{danji_id}"
            )

        for ep_url in endpoints:
            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(ep_url, headers=API_HEADERS)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if isinstance(data, dict):
                    item = data.get("item", data.get("items", [None]))
                    if isinstance(item, list):
                        item = item[0] if item else None
                    if item and isinstance(item, dict):
                        result = self._parse_zigbang_item(item)
                        if result:
                            return result

                    danji = data.get("danji", data)
                    if isinstance(danji, dict) and danji.get("name"):
                        return self._parse_zigbang_danji(danji, area_ho_id)
            except Exception as e:
                logger.debug("Zigbang apt API %s failed: %s", ep_url, e)
                continue

        return None

    def _parse_zigbang_danji(self, danji: dict, area_ho_id: str) -> ScrapeListingResponse | None:
        """Parse Zigbang danji (apartment complex) data."""
        name = danji.get("name", "")
        address = danji.get("address", "") or danji.get("jibun_address", "")
        if not name and not address:
            return None

        return ScrapeListingResponse(
            address=address,
            building_name=name,
            listing_text=f"{name} (직방 단지 정보)",
            listing_type="",
            property_type="아파트",
            source="직방",
        )

    async def _try_zigbang_og_llm(self, html: str, url: str) -> ScrapeListingResponse | None:
        """Extract info from Zigbang page using OG meta + LLM as a fallback."""
        meta = _extract_og_meta(html)
        title = meta.get("title", "")
        desc = meta.get("description", "")

        if not title and not desc:
            return None
        if title == "No.1 부동산 앱, 직방" and (not desc or "모든 매물의 정보를" in desc):
            return None

        combined_text = f"출처: 직방\nURL: {url}\n"
        if meta:
            combined_text += "메타 정보:\n" + "\n".join(f"  {k}: {v}" for k, v in meta.items()) + "\n\n"

        page_text = _clean_html(html)
        if len(page_text) > 100:
            combined_text += f"--- 페이지 텍스트 ---\n{page_text}"

        try:
            data = await self._llm.chat_json(SCRAPE_PROMPT, combined_text)
        except Exception as e:
            logger.warning("Zigbang OG+LLM extraction failed: %s", e)
            return None

        address = data.get("address", "")
        if address and not _looks_like_address(address):
            address = ""

        building = data.get("building_name", "")
        if building and building.lower() in ("네이버", "직방", "다방", "zigbang", "naver"):
            building = ""

        if not address and not building and not data.get("deposit"):
            return None

        return ScrapeListingResponse(
            address=address,
            building_name=building,
            deposit=data.get("deposit"),
            monthly_rent=data.get("monthly_rent"),
            area_sqm=data.get("area_sqm"),
            floor=data.get("floor", ""),
            listing_text=data.get("listing_text", ""),
            listing_type=data.get("listing_type", ""),
            property_type=data.get("property_type", ""),
            source="직방",
        )

    async def _try_zigbang_api_v2(self, item_id: str) -> ScrapeListingResponse | None:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://apis.zigbang.com/v2/items/{item_id}",
                    headers=API_HEADERS,
                )

            if resp.status_code != 200:
                return None

            data = resp.json()
            item = data.get("item", data)
            return self._parse_zigbang_item(item)
        except Exception as e:
            logger.debug("Zigbang v2 API failed: %s", e)
            return None

    async def _try_zigbang_api_v3_list(self, item_id: str) -> ScrapeListingResponse | None:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://apis.zigbang.com/v3/items?item_ids=[{item_id}]",
                    headers=API_HEADERS,
                )

            if resp.status_code != 200:
                return None

            data = resp.json()
            items = data.get("items", [])
            if not items:
                return None
            return self._parse_zigbang_item(items[0])
        except Exception as e:
            logger.debug("Zigbang v3 list API failed: %s", e)
            return None

    async def _try_zigbang_html(
        self, url: str, *, existing_html: str = "",
    ) -> ScrapeListingResponse | None:
        """Try extracting embedded JSON data from Zigbang HTML."""
        try:
            if existing_html:
                html = existing_html
            else:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(url, headers=BROWSER_HEADERS)
                if resp.status_code != 200:
                    return None
                html = resp.text
            import json as _json

            for pattern in [
                r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
                r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
                r'"itemDetail"\s*:\s*({.*?})\s*[,}]',
            ]:
                m = re.search(pattern, html, re.DOTALL)
                if m:
                    try:
                        embedded = _json.loads(m.group(1))
                        return self._parse_zigbang_item(embedded)
                    except _json.JSONDecodeError:
                        continue

            meta = _extract_og_meta(html)
            title = meta.get("title", "")
            desc = meta.get("description", "")
            if title == "No.1 부동산 앱, 직방" or not desc or "모든 매물의 정보를" in desc:
                return None

            return None
        except Exception as e:
            logger.debug("Zigbang HTML extraction failed: %s", e)
            return None

    def _parse_zigbang_item(self, item: dict) -> ScrapeListingResponse | None:
        if not item or not isinstance(item, dict):
            return None

        sales_type = item.get("sales_type", "") or item.get("salesType", "")
        listing_type = {"전세": "전세", "월세": "월세", "매매": "매매"}.get(sales_type, "") or _guess_listing_type(str(item))

        service_type = item.get("service_type", "") or item.get("serviceType", "")
        property_type = _guess_property_type(service_type) or "아파트"

        deposit = _safe_int(
            item.get("보증금액") or item.get("deposit") or item.get("price")
        )
        monthly = _safe_int(
            item.get("월세금액") or item.get("rent") or item.get("rentPrice")
        )

        address = (
            item.get("address", "")
            or item.get("jibun_address", "")
            or item.get("local_address", "")
            or item.get("road_address", "")
        )

        area = _safe_float(
            item.get("전용면적_m2")
            or item.get("exclusive_area")
            or item.get("exclusiveArea")
            or item.get("area")
        )

        building = (
            item.get("building_name", "")
            or item.get("buildingName", "")
            or item.get("title", "")
            or item.get("apt_name", "")
            or item.get("complex_name", "")
        )

        desc = item.get("description", "") or item.get("memo", "") or item.get("title", "")
        floor_str = str(item.get("floor", "") or item.get("floor_string", ""))

        if not address and not building and not area:
            return None

        return ScrapeListingResponse(
            address=address,
            building_name=building,
            deposit=deposit,
            monthly_rent=monthly if monthly and monthly > 0 else None,
            area_sqm=area,
            floor=floor_str,
            listing_text=desc,
            listing_type=listing_type or "전세",
            property_type=property_type,
            source="직방",
        )

    # ── 다방 ──

    async def _scrape_dabang(self, url: str) -> ScrapeListingResponse:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=BROWSER_HEADERS)
            if resp.status_code != 200:
                return await self._scrape_generic(url, "다방")

            html = resp.text
            final_url = str(resp.url)

            og_title_m = re.search(
                r'<meta\s+(?:property)=["\']og:title["\']\s+content=["\']([^"\']*)["\']', html,
            ) or re.search(
                r'content=["\']([^"\']*)["\'].*?property=["\']og:title["\']', html,
            )
            og_title = og_title_m.group(1) if og_title_m else ""

            if not og_title or "다방" not in og_title:
                return await self._scrape_generic(url, "다방")

            meta = _extract_og_meta(html)
            meta["og_title"] = og_title

            lat_m = re.search(r"m_lat=([\d.]+)", final_url)
            lng_m = re.search(r"m_lng=([\d.]+)", final_url)
            if lat_m and lng_m:
                meta["_lat"] = lat_m.group(1)
                meta["_lng"] = lng_m.group(1)

            return self._parse_dabang_og(meta, final_url)
        except Exception as e:
            logger.warning("Dabang scrape failed: %s", e)
            return await self._scrape_generic(url, "다방")

    def _parse_dabang_og(self, meta: dict[str, str], final_url: str) -> ScrapeListingResponse:
        og_title = meta.get("og_title", "") or meta.get("title", "")

        # Format: "[다방] 서울특별시 강남구 논현동, 아파트 매매 63억6300"
        cleaned = re.sub(r"^\[다방\]\s*", "", og_title)

        address = ""
        listing_type = ""
        property_type = ""
        deposit = None

        # Split by comma: "서울특별시 강남구 논현동" + "아파트 매매 63억6300"
        parts = cleaned.split(",", 1)
        if len(parts) >= 1:
            address = parts[0].strip()
        monthly_rent = None
        if len(parts) >= 2:
            detail = parts[1].strip()
            listing_type = _guess_listing_type(detail)
            property_type = _guess_property_type(detail)
            deposit = self._parse_dabang_price(detail)
            if listing_type == "월세":
                monthly_rent = self._parse_dabang_monthly(detail)

        # Extract room_id from URL for building name lookup
        room_id_m = re.search(r"detail_id=([a-f0-9]+)", final_url)
        if not room_id_m:
            room_id_m = re.search(r"/room/([a-f0-9]+)", final_url)
        if not room_id_m:
            room_id_m = re.search(r"/room/([a-f0-9]+)", meta.get("url", ""))

        area = None
        area_m = re.search(r"([\d.]+)\s*㎡", og_title)
        if area_m:
            area = _safe_float(area_m.group(1))

        src_lat = _safe_float(meta.get("_lat"))
        src_lng = _safe_float(meta.get("_lng"))

        return ScrapeListingResponse(
            address=address,
            building_name="",
            deposit=int(deposit) if deposit else None,
            monthly_rent=int(monthly_rent) if monthly_rent else None,
            area_sqm=area,
            floor="",
            listing_text=cleaned if cleaned != address else "",
            listing_type=listing_type or "매매",
            property_type=property_type or "아파트",
            source="다방",
            source_lat=src_lat if src_lat else None,
            source_lng=src_lng if src_lng else None,
        )

    @staticmethod
    def _parse_dabang_price(text: str) -> int | None:
        """Parse Korean price format like '63억6300', '3억', '5000' from Dabang title."""
        m = re.search(r"(\d+)억\s*(\d+)?", text)
        if m:
            eok = int(m.group(1))
            remain = int(m.group(2)) if m.group(2) else 0
            return eok * 10000 + remain

        m = re.search(r"(\d[\d,]+)\s*(?:만원|만)?(?:\s*/\s*(\d[\d,]+))?", text)
        if m:
            val = int(m.group(1).replace(",", ""))
            return val

        return None

    @staticmethod
    def _parse_dabang_monthly(text: str) -> int | None:
        """Parse monthly rent from format like '1000/50' or text containing 월세."""
        m = re.search(r"(\d[\d,]+)\s*/\s*(\d[\d,]+)", text)
        if m:
            return int(m.group(2).replace(",", ""))
        return None

    # ── 일반 (HTML + LLM 분석) ──

    async def _scrape_generic(self, url: str, source: str) -> ScrapeListingResponse:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=BROWSER_HEADERS)
                resp.raise_for_status()
                raw_html = resp.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return ScrapeListingResponse(
                    source=source,
                    listing_text="해당 매물 페이지를 찾을 수 없습니다 (404). 매물이 삭제되었거나 URL이 잘못되었을 수 있습니다.",
                )
            raise

        meta = _extract_og_meta(raw_html)
        page_text = _clean_html(raw_html)

        combined_text = " ".join(meta.values()) + " " + page_text

        is_spa_empty = (
            len(combined_text.strip()) < 15
            or (meta.get("title", "").startswith("Beyond Home") and "직방" in meta.get("description", ""))
            or "모든 매물의 정보를" in meta.get("description", "")
            or (not meta.get("title") and not meta.get("description") and len(combined_text.strip()) < 50)
        )
        if is_spa_empty:
            return ScrapeListingResponse(
                source=source,
                listing_text=(
                    "페이지에서 매물 정보를 추출할 수 없습니다.\n\n"
                    "해당 사이트는 JavaScript로 콘텐츠를 로딩하여 자동 추출이 어렵습니다.\n\n"
                    "매물 페이지의 정보를 직접 복사하여 입력해주세요:\n"
                    "• 주소, 매매가/보증금, 전용면적, 매물 설명"
                ),
            )

        input_text = ""
        if meta:
            input_text += "메타 정보:\n" + "\n".join(f"  {k}: {v}" for k, v in meta.items()) + "\n\n"
        input_text += f"출처: {source}\nURL: {url}\n\n--- 페이지 텍스트 ---\n{page_text}"

        try:
            data = await self._llm.chat_json(SCRAPE_PROMPT, input_text)
        except Exception as e:
            logger.warning("LLM extraction failed: %s", e)
            return ScrapeListingResponse(source=source, listing_text=page_text[:2000])

        address = data.get("address", "")
        if address and not _looks_like_address(address):
            logger.info("LLM extracted suspicious address, discarding: %s", address)
            address = ""

        building = data.get("building_name", "")
        if building and building.lower() in ("네이버", "직방", "다방", "zigbang", "naver"):
            building = ""

        return ScrapeListingResponse(
            address=address,
            building_name=building,
            deposit=data.get("deposit"),
            monthly_rent=data.get("monthly_rent"),
            area_sqm=data.get("area_sqm"),
            floor=data.get("floor", ""),
            listing_text=data.get("listing_text", ""),
            listing_type=data.get("listing_type", ""),
            property_type=data.get("property_type", ""),
            source=source,
        )
