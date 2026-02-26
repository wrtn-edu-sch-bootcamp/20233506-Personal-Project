from pydantic import BaseModel, Field
from enum import Enum


# ── Enums ──

class ListingType(str, Enum):
    JEONSE = "전세"
    MONTHLY = "월세"
    SALE = "매매"


class PropertyType(str, Enum):
    APT = "아파트"
    MULTIUNIT = "연립다세대"
    HOUSE = "단독다가구"
    OFFICETEL = "오피스텔"


class SuspiciousCategory(str, Enum):
    EXAGGERATION = "EXAGGERATION"
    MISLEADING = "MISLEADING"
    PRICE_BAIT = "PRICE_BAIT"
    OMISSION = "OMISSION"
    NORMAL = "NORMAL"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskGrade(str, Enum):
    SAFE = "안전"
    CAUTION = "주의"
    WARNING = "경고"
    DANGER = "위험"


class PriceAssessment(str, Enum):
    FAIR = "적정"
    UNDERPRICED = "저가의심"
    OVERPRICED = "고가의심"


# ── Request Models ──

class RegistryInput(BaseModel):
    """구조화된 등기부등본 입력 (직접 입력 or 텍스트 붙여넣기)."""
    owner: str | None = Field(None, description="소유자명")
    mortgage: float | None = Field(None, description="근저당 설정액 (만원)")
    seizure: bool = Field(False, description="압류/가압류 여부")
    trust: bool = Field(False, description="신탁등기 여부")
    raw_text: str | None = Field(None, description="등기부등본 원문 텍스트 (선택)")


class ListingAnalysisRequest(BaseModel):
    listing_text: str = Field(..., description="매물 설명 텍스트")
    listing_type: ListingType = Field(..., description="매물 유형")
    property_type: PropertyType = Field(PropertyType.APT, description="건물 유형")
    address: str = Field(..., description="주소")
    building_name: str = Field("", description="단지/건물명 (아파트, 오피스텔 등)")
    deposit: float = Field(..., description="보증금 (만원)")
    monthly_rent: float | None = Field(None, description="월세 (만원, 월세일 경우)")
    area_sqm: float = Field(..., description="면적 (㎡)")
    registry: RegistryInput | None = Field(None, description="등기부등본 정보 (선택)")


class TextAnalysisRequest(BaseModel):
    listing_text: str = Field(..., description="매물 설명 텍스트")


class RegistryAnalysisRequest(BaseModel):
    registry_text: str = Field(..., description="등기부등본 텍스트")
    deposit: float = Field(..., description="전세 보증금 (만원)")


class MarketPriceRequest(BaseModel):
    address: str = Field(..., description="주소")
    area_sqm: float = Field(..., description="면적 (㎡)")


# ── Response Models ──

class SuspiciousExpression(BaseModel):
    text: str
    category: SuspiciousCategory
    severity: Severity
    reason: str


class TextAnalysisResult(BaseModel):
    suspicious_expressions: list[SuspiciousExpression] = []
    analyzed: bool = Field(True, description="AI 분석이 정상 수행되었는지 여부")


class ExtractedInfo(BaseModel):
    price: str | None = None
    area: str | None = None
    floor: str | None = None
    location_claims: list[str] = []
    facilities: list[str] = []


class RecentTrade(BaseModel):
    price: float = Field(..., description="거래 금액 (만원)")
    area_sqm: float = 0
    year: int = 0
    month: int = 0
    day: int = 0
    dong: str = ""
    name: str = ""
    floor: int = 0
    trade_type: str = "매매"


class MonthlyTrend(BaseModel):
    month: str = Field("", description="YYYY-MM")
    avg_trade: float | None = None
    avg_rent: float | None = None
    trade_count: int = 0
    rent_count: int = 0


class MarketComparison(BaseModel):
    avg_market_price: float | None = None
    avg_sale_price: float | None = None
    deviation_rate: float | None = None
    assessment: PriceAssessment | None = None
    data_count: int = 0
    data_scope: str = Field("", description="데이터 범위 (같은 건물 / 같은 동 / 시군구 전체)")
    recent_trades: list[RecentTrade] = []
    monthly_trends: list[MonthlyTrend] = []


class RegistryAnalysis(BaseModel):
    owner: str | None = None
    mortgage: float = 0
    seizure: bool = False
    trust: bool = False


class InsuranceCheck(BaseModel):
    eligible: bool = Field(False, description="가입 가능 여부")
    verdict: str = Field("", description="판정 결과 요약")
    reasons: list[str] = Field(default_factory=list, description="판정 근거")
    tips: list[str] = Field(default_factory=list, description="가입 팁")


class JeonseRisk(BaseModel):
    jeonse_rate: float | None = None
    total_burden_ratio: float | None = Field(None, description="총 부담률 = (추정실채무액+보증금)/매매가 ×100")
    auction_recovery_risk: float | None = Field(None, description="경매안전율 = (추정실채무+보증금)/(매매가×낙찰가율) ×100")
    estimated_actual_debt: float | None = Field(None, description="추정 실제 채무액 (채권최고액 × 0.83)")
    risk_score: float = 0
    risk_grade: RiskGrade = RiskGrade.SAFE
    risk_factors: list[str] = []
    registry_analysis: RegistryAnalysis | None = None
    checklist: list[str] = []
    insurance_check: InsuranceCheck | None = None


class GeocodingResponse(BaseModel):
    address: str
    lat: float = 0
    lng: float = 0
    region_code: str = ""
    lawd_cd: str = ""
    region_1depth: str = ""
    region_2depth: str = ""
    region_3depth: str = ""


class ScrapeListingRequest(BaseModel):
    url: str = Field(..., description="매물 URL (직방, 다방, 네이버부동산 등)")


class ScrapeListingResponse(BaseModel):
    address: str = ""
    building_name: str = ""
    deposit: float | None = None
    monthly_rent: float | None = None
    area_sqm: float | None = None
    floor: str = ""
    listing_text: str = ""
    listing_type: str = ""
    property_type: str = ""
    source: str = ""
    source_lat: float | None = Field(None, exclude=True)
    source_lng: float | None = Field(None, exclude=True)


class RegistryFileResponse(BaseModel):
    owner: str | None = None
    mortgage: float | None = None
    seizure: bool = False
    trust: bool = False
    raw_text: str = ""
    risk_factors: list[str] = []


class AiReportSection(BaseModel):
    title: str
    icon: str = ""
    content: str
    verdict: str = ""


class LocationClaim(BaseModel):
    claim: str = Field(..., description="원문 위치 주장")
    category: str = Field("", description="시설 종류 (지하철역, 초등학교 등)")
    verified: bool = Field(False, description="검증 통과 여부")
    nearest_name: str = Field("", description="가장 가까운 시설명")
    actual_distance_m: int = Field(0, description="실제 직선 거리 (미터)")
    actual_walk_min: int = Field(0, description="추정 도보 시간 (분)")
    claimed_walk_min: int | None = Field(None, description="매물이 주장한 도보 시간")
    verdict: str = Field("", description="확인됨 / 과장됨 / 확인 불가")


class LocationVerification(BaseModel):
    claims: list[LocationClaim] = Field(default_factory=list)
    verified_count: int = 0
    exaggerated_count: int = 0


class NearbyFacility(BaseModel):
    name: str = ""
    category: str = ""
    distance_m: int = 0
    walk_min: int = 0


class NearbyFacilities(BaseModel):
    subway: list[NearbyFacility] = Field(default_factory=list)
    school: list[NearbyFacility] = Field(default_factory=list)
    mart: list[NearbyFacility] = Field(default_factory=list)
    hospital: list[NearbyFacility] = Field(default_factory=list)
    park: list[NearbyFacility] = Field(default_factory=list)
    convenience: list[NearbyFacility] = Field(default_factory=list)
    cafe: list[NearbyFacility] = Field(default_factory=list)
    bank: list[NearbyFacility] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    listing_type: ListingType = Field(ListingType.JEONSE, description="분석 매물 유형")
    reliability_score: float = Field(..., ge=0, le=100)
    reliability_grade: RiskGrade
    evaluation: str = Field("", description="AI 종합 평가 코멘트")
    ai_report: list[AiReportSection] = Field(default_factory=list, description="AI 상세 분석 리포트 섹션")
    text_analysis: TextAnalysisResult
    extracted_info: ExtractedInfo
    market_comparison: MarketComparison
    location_verification: LocationVerification | None = None
    nearby_facilities: NearbyFacilities | None = None
    jeonse_risk: JeonseRisk | None = None
