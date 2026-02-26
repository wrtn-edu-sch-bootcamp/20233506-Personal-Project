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

        if ref_price is None or ref_price == 0:
            return MarketComparison(
                avg_sale_price=data.avg_trade_price,
                data_scope=scope,
                recent_trades=recent_trades[:MAX_DISPLAY],
                monthly_trends=monthly_trends,
            )

        deviation = round(((listing_price - ref_price) / ref_price) * 100, 1)

        if deviation < -20:
            assessment = PriceAssessment.UNDERPRICED
        elif deviation > 20:
            assessment = PriceAssessment.OVERPRICED
        else:
            assessment = PriceAssessment.FAIR

        return MarketComparison(
            avg_market_price=ref_price,
            avg_sale_price=data.avg_trade_price,
            deviation_rate=deviation,
            assessment=assessment,
            data_count=count,
            data_scope=scope,
            recent_trades=recent_trades[:MAX_DISPLAY],
            monthly_trends=monthly_trends,
        )
