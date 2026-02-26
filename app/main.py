import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from fastapi import UploadFile, File

from app.models.schemas import (
    ListingAnalysisRequest,
    TextAnalysisRequest,
    RegistryAnalysisRequest,
    MarketPriceRequest,
    ScrapeListingRequest,
    ScrapeListingResponse,
    RegistryFileResponse,
    AnalysisReport,
    TextAnalysisResult,
    JeonseRisk,
    MarketComparison,
    GeocodingResponse,
)
from app.modules.report_generator import ReportGenerator
from app.modules.text_analyzer import TextAnalyzer
from app.modules.jeonse_analyzer import JeonseAnalyzer
from app.modules.market_comparator import MarketComparator
from app.services.llm_service import LLMService
from app.services.real_estate_api import RealEstateAPIService
from app.services.kakao_map_service import KakaoMapService
from app.services.listing_scraper import ListingScraper
from app.services.zigbang_api import ZigbangAPIService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SafeHome API starting up")
    yield
    logger.info("SafeHome API shutting down")


app = FastAPI(
    title="SafeHome API",
    description="AI 기반 부동산 매물 신뢰도 분석 및 전세사기 위험 탐지 시스템",
    version="0.1.0",
    lifespan=lifespan,
)

import os

_allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "SafeHome"}


@app.post("/api/analyze", response_model=AnalysisReport)
async def analyze_listing(req: ListingAnalysisRequest):
    generator = ReportGenerator()
    return await generator.generate(req)


@app.post("/api/analyze/text", response_model=TextAnalysisResult)
async def analyze_text(req: TextAnalysisRequest):
    llm = LLMService()
    analyzer = TextAnalyzer(llm)
    result, _ = await analyzer.analyze(req.listing_text)
    return result


@app.post("/api/analyze/registry", response_model=JeonseRisk)
async def analyze_registry(req: RegistryAnalysisRequest):
    llm = LLMService()
    analyzer = JeonseAnalyzer(llm)
    return await analyzer.analyze(
        deposit=req.deposit,
        market_price=None,
        registry_text=req.registry_text,
    )


@app.get("/api/market-price", response_model=MarketComparison)
async def get_market_price(
    address: str,
    area_sqm: float,
    listing_price: float,
    listing_type: str = "전세",
    property_type: str = "아파트",
    building_name: str = "",
):
    from app.models.schemas import ListingType as LT, PropertyType as PT
    service = RealEstateAPIService()
    comparator = MarketComparator(service)
    return await comparator.compare(
        address, area_sqm, listing_price,
        listing_type=LT(listing_type),
        property_type=PT(property_type),
        building_name=building_name,
    )


@app.post("/api/scrape-listing", response_model=ScrapeListingResponse)
async def scrape_listing(req: ScrapeListingRequest):
    scraper = ListingScraper()
    result = await scraper.scrape(req.url)

    address_needs_upgrade = (
        not result.address
        or (result.address and not _has_specific_address(result.address))
    )

    if address_needs_upgrade:
        try:
            kakao = KakaoMapService()
            upgraded = False

            if result.building_name:
                query = f"{result.address} {result.building_name}".strip() if result.address else result.building_name
                geo = await kakao.geocode(query)
                if geo and geo.address and geo.lat:
                    result.address = geo.address
                    upgraded = True
                    logger.info("Address from building name '%s' → '%s'", query, geo.address)

            if not upgraded and result.source_lat and result.source_lng:
                addr = await kakao.reverse_geocode(result.source_lat, result.source_lng)
                if addr:
                    result.address = addr
                    logger.info("Address from coordinates → '%s'", addr)

        except Exception as e:
            logger.debug("Address auto-fill failed: %s", e)

    return result


def _has_specific_address(addr: str) -> bool:
    """Check if address has a specific lot/road number, not just 동/구 level."""
    import re
    if re.search(r"\d{1,5}(-\d{1,5})?$", addr.strip()):
        return True
    if re.search(r"\d{1,5}번길|\d{1,5}로\s", addr):
        return True
    return False


@app.post("/api/analyze/registry/file", response_model=RegistryFileResponse)
async def analyze_registry_file(file: UploadFile = File(...)):
    content = await file.read()
    llm = LLMService()

    if file.content_type and "pdf" in file.content_type:
        import base64
        b64 = base64.b64encode(content).decode()
        text = await llm.chat(
            "이 PDF는 등기부등본입니다. 전체 내용을 텍스트로 변환해주세요.",
            f"[PDF 파일 - base64: {b64[:500]}... (truncated)]",
        )
    else:
        import base64
        b64 = base64.b64encode(content).decode()
        mime = file.content_type or "image/jpeg"
        text = await llm.extract_from_image(b64, mime)

    analyzer = JeonseAnalyzer(llm)
    registry, risk_factors = await analyzer._analyze_registry(text)
    return RegistryFileResponse(
        owner=registry.owner,
        mortgage=registry.mortgage,
        seizure=registry.seizure,
        trust=registry.trust,
        raw_text=text[:3000],
        risk_factors=risk_factors,
    )


@app.get("/api/geocode", response_model=GeocodingResponse)
async def geocode_address(address: str):
    kakao = KakaoMapService()
    result = await kakao.geocode(address)
    if result is None:
        return GeocodingResponse(address=address)
    return GeocodingResponse(
        address=result.address,
        lat=result.lat,
        lng=result.lng,
        region_code=result.region_code,
        lawd_cd=result.lawd_cd,
        region_1depth=result.region_1depth,
        region_2depth=result.region_2depth,
        region_3depth=result.region_3depth,
    )


# ── 직방 매물 검색 ──

@app.get("/api/zigbang/search")
async def zigbang_search(q: str):
    """직방 지역/주소 키워드 검색."""
    service = ZigbangAPIService()
    results = await service.search_region(q)
    return [
        {"name": r.name, "lat": r.lat, "lng": r.lng, "id": r.id, "type": r.type}
        for r in results
    ]


@app.get("/api/zigbang/listings")
async def zigbang_listings(
    lat: float,
    lng: float,
    sales_type: str = "전세",
    service_type: str = "원룸",
):
    """좌표 기반 직방 매물 목록 조회."""
    service = ZigbangAPIService()
    items = await service.get_listings(lat, lng, sales_type, service_type)
    return [
        {
            "item_id": it.item_id,
            "sales_type": it.sales_type,
            "service_type": it.service_type,
            "deposit": it.deposit,
            "rent": it.rent,
            "area_m2": it.area_m2,
            "floor": it.floor,
            "address": it.address,
            "title": it.title,
            "image_url": it.image_url,
            "manage_cost": it.manage_cost,
        }
        for it in items
        if it.item_id
    ]


@app.get("/api/zigbang/detail/{item_id}")
async def zigbang_detail(item_id: int):
    """직방 매물 상세 조회."""
    service = ZigbangAPIService()
    item = await service.get_listing_detail(item_id)
    if not item:
        return {"error": "매물을 찾을 수 없습니다"}
    return {
        "item_id": item.item_id,
        "sales_type": item.sales_type,
        "service_type": item.service_type,
        "deposit": item.deposit,
        "rent": item.rent,
        "area_m2": item.area_m2,
        "floor": item.floor,
        "address": item.address,
        "title": item.title,
        "description": item.description,
        "image_url": item.image_url,
        "manage_cost": item.manage_cost,
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    port = int(os.getenv("PORT", settings.app_port))
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=port,
        reload=settings.app_debug,
    )
