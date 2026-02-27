import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from dateutil.relativedelta import relativedelta

import httpx

from app.config import get_settings
from app.models.schemas import PropertyType, ListingType
from app.services.kakao_map_service import KakaoMapService, GeocodingResult

logger = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/1613000"

TRADE_ENDPOINTS: dict[PropertyType, str] = {
    PropertyType.APT: "RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    PropertyType.MULTIUNIT: "RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
    PropertyType.HOUSE: "RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade",
    PropertyType.OFFICETEL: "RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
}

RENT_ENDPOINTS: dict[PropertyType, str] = {
    PropertyType.APT: "RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
    PropertyType.MULTIUNIT: "RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    PropertyType.HOUSE: "RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
    PropertyType.OFFICETEL: "RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
}

AREA_TOLERANCE_SQM = 10.0
SAME_BUILDING_AREA_TOLERANCE = 15.0
WIDE_AREA_TOLERANCE_SQM = 25.0
QUERY_MONTHS = 12
MAX_RECENT_TRADES = 15
MIN_TIER_RECORDS = 3
API_CONCURRENT_LIMIT = 4

SCOPE_BUILDING = "같은 건물"
SCOPE_BUILDING_FMT = "같은 건물 · {area_min:.0f}~{area_max:.0f}㎡"
SCOPE_DONG = "같은 동/읍/면"
SCOPE_DONG_FMT = "같은 동/읍/면 · {area_min:.0f}~{area_max:.0f}㎡"
SCOPE_DISTRICT = "시/군/구 전체"
SCOPE_DISTRICT_FMT = "시/군/구 전체 · {area_min:.0f}~{area_max:.0f}㎡"
SCOPE_DISTRICT_WIDE_FMT = "시/군/구 전체 (유사 평수) · {area_min:.0f}~{area_max:.0f}㎡"

MOCK_SALE_PRICES: dict[str, float] = {
    "강남구": 65_000, "서초구": 60_000, "송파구": 50_000,
    "마포구": 40_000, "용산구": 55_000, "성동구": 42_000,
    "영등포구": 35_000, "default": 10_000,
}
MOCK_RENT_RATIOS: dict[str, float] = {
    "강남구": 0.55, "서초구": 0.58, "송파구": 0.62,
    "마포구": 0.65, "용산구": 0.60, "성동구": 0.64,
    "영등포구": 0.68, "default": 0.65,
}


@dataclass
class TradeRecord:
    price: float
    area_sqm: float
    year: int
    month: int
    day: int
    dong: str = ""
    name: str = ""
    floor: int = 0


@dataclass
class RentRecord:
    deposit: float
    monthly_rent: float
    area_sqm: float
    year: int
    month: int
    day: int
    dong: str = ""
    name: str = ""
    floor: int = 0


@dataclass
class MonthlyStats:
    month: str
    avg_trade: float | None = None
    avg_rent: float | None = None
    trade_count: int = 0
    rent_count: int = 0


@dataclass
class MarketPriceData:
    source: str
    avg_trade_price: float | None = None
    avg_rent_deposit: float | None = None
    trade_count: int = 0
    rent_count: int = 0
    trade_scope: str = ""
    rent_scope: str = ""
    region: str = ""
    lat: float = 0
    lng: float = 0
    recent_trade_records: list[TradeRecord] = field(default_factory=list)
    recent_rent_records: list[RentRecord] = field(default_factory=list)
    monthly_stats: list[MonthlyStats] = field(default_factory=list)


def _normalize_name(name: str) -> str:
    n = name.strip()
    n = re.sub(r'\s*(아파트|APT|apt|오피스텔)\s*$', '', n, flags=re.IGNORECASE)
    return n.strip()


def _name_matches(query: str, record_name: str) -> bool:
    """Check if building names match (fuzzy containment)."""
    if not query or not record_name:
        return False
    q = _normalize_name(query)
    r = _normalize_name(record_name)
    if not q or not r:
        return False
    return q in r or r in q


def _dong_matches(geo_dong: str, record_dong: str) -> bool:
    """Check if dong/eup/myeon names match."""
    if not geo_dong or not record_dong:
        return False
    g = geo_dong.strip()
    r = record_dong.strip()
    return g in r or r in g


class RealEstateAPIService:
    """국토교통부 실거래가 API — 건물유형별 매매/전월세 데이터 조회."""

    def __init__(self, kakao: KakaoMapService | None = None) -> None:
        settings = get_settings()
        self._api_key = settings.real_estate_api_key
        self._kakao = kakao or KakaoMapService()

    async def get_market_price(
        self,
        address: str,
        area_sqm: float,
        property_type: PropertyType = PropertyType.APT,
        listing_type: ListingType = ListingType.JEONSE,
        building_name: str = "",
    ) -> MarketPriceData:
        geo = await self._kakao.geocode(address)

        if not self._api_key or not geo or not geo.lawd_cd:
            logger.info("Using mock data (api_key=%s, geo=%s)", bool(self._api_key), geo is not None)
            return self._mock_market_price(address, area_sqm, geo)

        try:
            data = await self._fetch_prices(geo, area_sqm, property_type, listing_type, building_name)
            logger.info(
                "API result: source=%s, trade_avg=%s(%s, %d건), rent_avg=%s(%s, %d건), recent=%d+%d",
                data.source, data.avg_trade_price, data.trade_scope, data.trade_count,
                data.avg_rent_deposit, data.rent_scope, data.rent_count,
                len(data.recent_trade_records), len(data.recent_rent_records),
            )
            return data
        except Exception as e:
            logger.warning("Real estate API failed, using mock: %s", e)
            return self._mock_market_price(address, area_sqm, geo)

    # ── 실거래 API 호출 (12개월, 병렬) ──

    async def _fetch_prices(
        self,
        geo: GeocodingResult,
        area_sqm: float,
        property_type: PropertyType,
        listing_type: ListingType,
        building_name: str = "",
    ) -> MarketPriceData:
        months = self._recent_months(QUERY_MONTHS)
        region_label = f"{geo.region_1depth} {geo.region_2depth} {geo.region_3depth}".strip()
        dong_name = geo.region_3depth.strip()
        bname = _normalize_name(building_name)

        avg_trade: float | None = None
        trade_count = 0
        trade_scope = ""
        avg_rent: float | None = None
        rent_count = 0
        rent_scope = ""
        recent_trades: list[TradeRecord] = []
        recent_rents: list[RentRecord] = []
        all_trade_records: list[TradeRecord] = []
        all_rent_records: list[RentRecord] = []

        need_trade = listing_type in (ListingType.SALE, ListingType.JEONSE)
        need_rent = listing_type in (ListingType.JEONSE, ListingType.MONTHLY)

        if need_trade:
            all_trade_records = await self._query_trade(geo.lawd_cd, property_type, months)
            logger.info("Trade raw records: %d (lawd=%s, dong=%s, building=%s)", len(all_trade_records), geo.lawd_cd, dong_name, bname)
            avg_trade, trade_count, recent_trades, trade_scope = self._tiered_filter_trades(
                all_trade_records, area_sqm, bname, dong_name,
            )

        if need_rent:
            all_rent_raw = await self._query_rent(geo.lawd_cd, property_type, months)
            logger.info("Rent raw records: %d (lawd=%s)", len(all_rent_raw), geo.lawd_cd)
            all_rent_records = [r for r in all_rent_raw if r.monthly_rent == 0]
            avg_rent, rent_count, recent_rents, rent_scope = self._tiered_filter_rents(
                all_rent_records, area_sqm, bname, dong_name,
            )

        monthly = self._compute_monthly_stats(
            all_trade_records, all_rent_records, area_sqm, months,
        )

        return MarketPriceData(
            source="api",
            avg_trade_price=avg_trade,
            avg_rent_deposit=avg_rent,
            trade_count=trade_count,
            rent_count=rent_count,
            trade_scope=trade_scope,
            rent_scope=rent_scope,
            region=region_label,
            lat=geo.lat,
            lng=geo.lng,
            recent_trade_records=recent_trades,
            recent_rent_records=recent_rents,
            monthly_stats=monthly,
        )

    # ── 3단계 에스컬레이션 필터 ──

    @staticmethod
    def _tiered_filter_trades(
        records: list[TradeRecord],
        area_sqm: float,
        building_name: str,
        dong_name: str,
    ) -> tuple[float | None, int, list[TradeRecord], str]:
        tier1_building: list[TradeRecord] = []
        tier2_dong: list[TradeRecord] = []
        tier3_district: list[TradeRecord] = []
        tier4_wide: list[TradeRecord] = []

        for r in records:
            is_same_building = _name_matches(building_name, r.name)
            is_same_dong = _dong_matches(dong_name, r.dong)
            is_area_wide = abs(r.area_sqm - area_sqm) <= SAME_BUILDING_AREA_TOLERANCE
            is_area_ok = abs(r.area_sqm - area_sqm) <= AREA_TOLERANCE_SQM
            is_area_wider = abs(r.area_sqm - area_sqm) <= WIDE_AREA_TOLERANCE_SQM

            if is_same_building and is_area_wide:
                tier1_building.append(r)
            if is_same_dong and is_area_ok:
                tier2_dong.append(r)
            if is_area_ok:
                tier3_district.append(r)
            if is_area_wider:
                tier4_wide.append(r)

        if len(tier1_building) >= MIN_TIER_RECORDS:
            targets = tier1_building
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_BUILDING_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier1 (building=%s): %d trades", building_name, len(targets))
        elif len(tier2_dong) >= MIN_TIER_RECORDS:
            targets = tier2_dong
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_DONG_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier2 (dong=%s): %d trades", dong_name, len(targets))
        elif tier3_district:
            targets = tier3_district
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_DISTRICT_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier3 (district): %d trades", len(targets))
        elif tier4_wide:
            targets = tier4_wide
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_DISTRICT_WIDE_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier4 (wide area ±25㎡): %d trades", len(targets))
        else:
            return None, 0, [], ""

        avg_price = round(sum(r.price for r in targets) / len(targets))
        sorted_recs = sorted(targets, key=lambda r: (r.year, r.month, r.day), reverse=True)
        return avg_price, len(targets), sorted_recs[:MAX_RECENT_TRADES], scope

    @staticmethod
    def _tiered_filter_rents(
        records: list[RentRecord],
        area_sqm: float,
        building_name: str,
        dong_name: str,
    ) -> tuple[float | None, int, list[RentRecord], str]:
        tier1_building: list[RentRecord] = []
        tier2_dong: list[RentRecord] = []
        tier3_district: list[RentRecord] = []
        tier4_wide: list[RentRecord] = []

        for r in records:
            is_same_building = _name_matches(building_name, r.name)
            is_same_dong = _dong_matches(dong_name, r.dong)
            is_area_wide = abs(r.area_sqm - area_sqm) <= SAME_BUILDING_AREA_TOLERANCE
            is_area_ok = abs(r.area_sqm - area_sqm) <= AREA_TOLERANCE_SQM
            is_area_wider = abs(r.area_sqm - area_sqm) <= WIDE_AREA_TOLERANCE_SQM

            if is_same_building and is_area_wide:
                tier1_building.append(r)
            if is_same_dong and is_area_ok:
                tier2_dong.append(r)
            if is_area_ok:
                tier3_district.append(r)
            if is_area_wider:
                tier4_wide.append(r)

        if len(tier1_building) >= MIN_TIER_RECORDS:
            targets = tier1_building
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_BUILDING_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier1 rent (building=%s): %d records", building_name, len(targets))
        elif len(tier2_dong) >= MIN_TIER_RECORDS:
            targets = tier2_dong
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_DONG_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier2 rent (dong=%s): %d records", dong_name, len(targets))
        elif tier3_district:
            targets = tier3_district
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_DISTRICT_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier3 rent (district): %d records", len(targets))
        elif tier4_wide:
            targets = tier4_wide
            areas = [r.area_sqm for r in targets]
            scope = SCOPE_DISTRICT_WIDE_FMT.format(area_min=min(areas), area_max=max(areas))
            logger.info("Tier4 rent (wide area ±25㎡): %d records", len(targets))
        else:
            return None, 0, [], ""

        avg_deposit = round(sum(r.deposit for r in targets) / len(targets))
        sorted_recs = sorted(targets, key=lambda r: (r.year, r.month, r.day), reverse=True)
        return avg_deposit, len(targets), sorted_recs[:MAX_RECENT_TRADES], scope

    # ── API 호출 (병렬) ──

    async def _query_trade(
        self, lawd_cd: str, prop: PropertyType, months: list[str]
    ) -> list[TradeRecord]:
        endpoint = TRADE_ENDPOINTS[prop]
        return await self._query_parallel(endpoint, lawd_cd, months, self._parse_trade_xml)

    async def _query_rent(
        self, lawd_cd: str, prop: PropertyType, months: list[str]
    ) -> list[RentRecord]:
        endpoint = RENT_ENDPOINTS[prop]
        return await self._query_parallel(endpoint, lawd_cd, months, self._parse_rent_xml)

    async def _query_parallel(self, endpoint, lawd_cd, months, parser):
        all_records = []
        sem = asyncio.Semaphore(API_CONCURRENT_LIMIT)

        async def fetch_one(ym: str):
            async with sem:
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(
                            f"{BASE_URL}/{endpoint}",
                            params={
                                "serviceKey": self._api_key,
                                "LAWD_CD": lawd_cd,
                                "DEAL_YMD": ym,
                                "numOfRows": "1000",
                                "pageNo": "1",
                            },
                        )
                        resp.raise_for_status()
                        return parser(resp.text)
                except Exception as e:
                    logger.warning("Query failed for %s/%s: %s", lawd_cd, ym, e)
                    return []

        results = await asyncio.gather(*(fetch_one(ym) for ym in months))
        for recs in results:
            all_records.extend(recs)
        return all_records

    # ── XML 파싱 ──

    @staticmethod
    def _parse_trade_xml(xml_text: str) -> list[TradeRecord]:
        records: list[TradeRecord] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.error("Failed to parse trade XML")
            return records

        for item in root.iter("item"):
            try:
                price_text = (item.findtext("거래금액") or item.findtext("dealAmount") or "0")
                price = float(price_text.strip().replace(",", ""))
                area = float((item.findtext("전용면적") or item.findtext("excluUseAr") or "0").strip())
                year = int((item.findtext("년") or item.findtext("dealYear") or "0").strip())
                month = int((item.findtext("월") or item.findtext("dealMonth") or "0").strip())
                day = int((item.findtext("일") or item.findtext("dealDay") or "0").strip())
                dong = (item.findtext("법정동") or item.findtext("umdNm") or "").strip()
                name = (item.findtext("아파트") or item.findtext("aptNm") or "").strip()
                floor = int((item.findtext("층") or item.findtext("floor") or "0").strip())

                records.append(TradeRecord(
                    price=price, area_sqm=area,
                    year=year, month=month, day=day,
                    dong=dong, name=name, floor=floor,
                ))
            except (ValueError, TypeError) as e:
                logger.debug("Skipping trade record: %s", e)

        return records

    @staticmethod
    def _parse_rent_xml(xml_text: str) -> list[RentRecord]:
        records: list[RentRecord] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.error("Failed to parse rent XML")
            return records

        for item in root.iter("item"):
            try:
                deposit_text = (item.findtext("보증금액") or item.findtext("deposit") or "0")
                deposit = float(deposit_text.strip().replace(",", ""))
                rent_text = (item.findtext("월세금액") or item.findtext("monthlyRent") or "0")
                monthly = float(rent_text.strip().replace(",", ""))
                area = float((item.findtext("전용면적") or item.findtext("excluUseAr") or "0").strip())
                year = int((item.findtext("년") or item.findtext("dealYear") or "0").strip())
                month = int((item.findtext("월") or item.findtext("dealMonth") or "0").strip())
                day = int((item.findtext("일") or item.findtext("dealDay") or "0").strip())
                dong = (item.findtext("법정동") or item.findtext("umdNm") or "").strip()
                name = (item.findtext("아파트") or item.findtext("aptNm") or "").strip()
                floor = int((item.findtext("층") or item.findtext("floor") or "0").strip())

                records.append(RentRecord(
                    deposit=deposit, monthly_rent=monthly, area_sqm=area,
                    year=year, month=month, day=day,
                    dong=dong, name=name, floor=floor,
                ))
            except (ValueError, TypeError) as e:
                logger.debug("Skipping rent record: %s", e)

        return records

    # ── 월별 집계 ──

    @staticmethod
    def _compute_monthly_stats(
        trades: list[TradeRecord],
        rents: list[RentRecord],
        area_sqm: float,
        months: list[str],
    ) -> list[MonthlyStats]:
        from collections import defaultdict
        trade_by_month: dict[str, list[float]] = defaultdict(list)
        rent_by_month: dict[str, list[float]] = defaultdict(list)

        tolerance = AREA_TOLERANCE_SQM
        trade_matched = sum(1 for r in trades if abs(r.area_sqm - area_sqm) <= tolerance)
        rent_matched = sum(1 for r in rents if abs(r.area_sqm - area_sqm) <= tolerance)
        if trade_matched < 3 and rent_matched < 3:
            tolerance = WIDE_AREA_TOLERANCE_SQM

        for r in trades:
            if abs(r.area_sqm - area_sqm) <= tolerance:
                key = f"{r.year}-{r.month:02d}"
                trade_by_month[key].append(r.price)
        for r in rents:
            if abs(r.area_sqm - area_sqm) <= tolerance:
                key = f"{r.year}-{r.month:02d}"
                rent_by_month[key].append(r.deposit)

        result: list[MonthlyStats] = []
        for ym in reversed(months):
            label = f"{ym[:4]}-{ym[4:]}"
            tp = trade_by_month.get(label, [])
            rp = rent_by_month.get(label, [])
            result.append(MonthlyStats(
                month=label,
                avg_trade=round(sum(tp) / len(tp)) if tp else None,
                avg_rent=round(sum(rp) / len(rp)) if rp else None,
                trade_count=len(tp),
                rent_count=len(rp),
            ))
        return result

    # ── 유틸 ──

    @staticmethod
    def _recent_months(count: int) -> list[str]:
        now = datetime.now()
        return [
            (now - relativedelta(months=i)).strftime("%Y%m")
            for i in range(count)
        ]

    # ── Mock 데이터 ──

    def _mock_market_price(
        self,
        address: str,
        area_sqm: float,
        geo: GeocodingResult | None = None,
    ) -> MarketPriceData:
        district = geo.region_2depth if geo else ""
        if not district:
            for name in MOCK_SALE_PRICES:
                if name in address:
                    district = name
                    break

        sale_per_pyeong = MOCK_SALE_PRICES.get(district, MOCK_SALE_PRICES["default"])
        rent_ratio = MOCK_RENT_RATIOS.get(district, MOCK_RENT_RATIOS["default"])
        pyeong = area_sqm / 3.3058

        avg_trade = round(sale_per_pyeong * pyeong)
        avg_rent = round(avg_trade * rent_ratio)

        return MarketPriceData(
            source="mock",
            avg_trade_price=avg_trade,
            avg_rent_deposit=avg_rent,
            trade_count=0,
            rent_count=0,
            region=(f"{geo.region_1depth} {geo.region_2depth} {geo.region_3depth}".strip() if geo else district),
            lat=geo.lat if geo else 0,
            lng=geo.lng if geo else 0,
        )


def get_real_estate_service() -> RealEstateAPIService:
    return RealEstateAPIService()
