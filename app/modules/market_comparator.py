import logging

from app.models.schemas import (
    ListingType,
    PropertyType,
    MarketComparison,
    MonthlyTrend,
    PriceAssessment,
    RecentTrade,
)
from app.services.real_estate_api import RealEstateAPIService

logger = logging.getLogger(__name__)

MAX_DISPLAY = 15


def _assess_deviation(deviation: float) -> PriceAssessment:
    """5-level price assessment based on KB부동산/한국부동산원 industry standards."""
    abs_dev = abs(deviation)
    if abs_dev <= 5:
        return PriceAssessment.VERY_FAIR
    if abs_dev <= 10:
        return PriceAssessment.FAIR
    if abs_dev <= 15:
        return PriceAssessment.SLIGHTLY_HIGH if deviation > 0 else PriceAssessment.SLIGHTLY_LOW
    if abs_dev <= 25:
        return PriceAssessment.OVERPRICED if deviation > 0 else PriceAssessment.UNDERPRICED
    return PriceAssessment.SIGNIFICANTLY_HIGH if deviation > 0 else PriceAssessment.SIGNIFICANTLY_LOW


def _compute_trend(monthly_stats: list, listing_type: ListingType) -> str:
    """Compare recent 3-month avg vs 12-month avg to detect trend."""
    if len(monthly_stats) < 4:
        return "알수없음"

    def _avg_price(stats: list) -> float | None:
        prices = []
        for s in stats:
            p = s.avg_rent if listing_type != ListingType.SALE else s.avg_trade
            if p is not None and p > 0:
                prices.append(p)
        return sum(prices) / len(prices) if prices else None

    recent = monthly_stats[-3:]
    all_stats = monthly_stats

    recent_avg = _avg_price(recent)
    full_avg = _avg_price(all_stats)

    if recent_avg is None or full_avg is None or full_avg == 0:
        return "알수없음"

    change_rate = ((recent_avg - full_avg) / full_avg) * 100
    if change_rate > 3:
        return "상승"
    if change_rate < -3:
        return "하락"
    return "안정"


def _compute_jeonse_rate(avg_rent: float | None, avg_trade: float | None) -> tuple[float | None, str]:
    """Compute jeonse-to-sale ratio and risk level (국토연구원 기준)."""
    if not avg_rent or not avg_trade or avg_trade == 0:
        return None, ""
    rate = round((avg_rent / avg_trade) * 100, 1)
    if rate <= 60:
        return rate, "안전"
    if rate <= 70:
        return rate, "보통"
    if rate <= 80:
        return rate, "주의"
    return rate, "위험"


def _build_source_label(scope: str, listing_type: ListingType) -> str:
    """Build human-readable data source description."""
    base = "국토교통부 실거래가 공개시스템"
    criteria = "KB부동산 시세 기준"
    trend_src = "한국부동산원 월간 동향 기준"
    return f"{base} ({scope}) · 평가 기준: {criteria} · 추세 판단: {trend_src}"


class MarketComparator:
    def __init__(self, real_estate_service: RealEstateAPIService) -> None:
        self._api = real_estate_service

    async def compare(
        self,
        address: str,
        area_sqm: float,
        listing_price: float,
        listing_type: ListingType = ListingType.JEONSE,
        property_type: PropertyType = PropertyType.APT,
        building_name: str = "",
    ) -> MarketComparison:
        data = await self._api.get_market_price(
            address, area_sqm, property_type, listing_type,
            building_name=building_name,
        )

        if listing_type == ListingType.SALE:
            ref_price = data.avg_trade_price
            count = data.trade_count
            scope = data.trade_scope
        else:
            ref_price = data.avg_rent_deposit
            count = data.rent_count
            scope = data.rent_scope

        recent_trades: list[RecentTrade] = []
        for r in data.recent_trade_records:
            recent_trades.append(RecentTrade(
                price=r.price, area_sqm=r.area_sqm,
                year=r.year, month=r.month, day=r.day,
                dong=r.dong, name=r.name, floor=r.floor,
                trade_type="매매",
            ))
        for r in data.recent_rent_records:
            recent_trades.append(RecentTrade(
                price=r.deposit, area_sqm=r.area_sqm,
                year=r.year, month=r.month, day=r.day,
                dong=r.dong, name=r.name, floor=r.floor,
                trade_type="전세",
            ))
        recent_trades.sort(key=lambda t: (t.year, t.month, t.day), reverse=True)

        monthly_trends = [
            MonthlyTrend(
                month=s.month,
                avg_trade=s.avg_trade,
                avg_rent=s.avg_rent,
                trade_count=s.trade_count,
                rent_count=s.rent_count,
            )
            for s in data.monthly_stats
        ]

        price_trend = _compute_trend(data.monthly_stats, listing_type)
        jeonse_rate_market, jeonse_rate_risk = _compute_jeonse_rate(
            data.avg_rent_deposit, data.avg_trade_price,
        )
        data_source = _build_source_label(scope, listing_type)

        if ref_price is None or ref_price == 0:
            return MarketComparison(
                avg_sale_price=data.avg_trade_price,
                data_scope=scope,
                recent_trades=recent_trades[:MAX_DISPLAY],
                monthly_trends=monthly_trends,
                price_trend=price_trend,
                jeonse_rate_market=jeonse_rate_market,
                jeonse_rate_risk=jeonse_rate_risk,
                data_source=data_source,
            )

        deviation = round(((listing_price - ref_price) / ref_price) * 100, 1)
        assessment = _assess_deviation(deviation)

        return MarketComparison(
            avg_market_price=ref_price,
            avg_sale_price=data.avg_trade_price,
            deviation_rate=deviation,
            assessment=assessment,
            data_count=count,
            data_scope=scope,
            recent_trades=recent_trades[:MAX_DISPLAY],
            monthly_trends=monthly_trends,
            price_trend=price_trend,
            jeonse_rate_market=jeonse_rate_market,
            jeonse_rate_risk=jeonse_rate_risk,
            data_source=data_source,
        )
