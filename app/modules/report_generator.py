import asyncio
import logging

from app.models.schemas import (
    ListingAnalysisRequest,
    ListingType,
    AnalysisReport,
    AiReportSection,
    TextAnalysisResult,
    MarketComparison,
    RegistryAnalysis,
    LocationVerification,
    NearbyFacilities,
)
from app.modules.text_analyzer import TextAnalyzer
from app.modules.market_comparator import MarketComparator
from app.modules.jeonse_analyzer import JeonseAnalyzer
from app.services.llm_service import LLMService
from app.services.real_estate_api import RealEstateAPIService
from app.services.kakao_map_service import KakaoMapService
from app.services.location_verifier import LocationVerifier
from app.utils.scoring import calculate_reliability_score, score_to_grade

logger = logging.getLogger(__name__)

EVALUATION_PROMPT_SALE = """당신은 부동산 매매 전문 분석가입니다. 아래 분석 결과를 바탕으로 일반인이 이해할 수 있는 종합 평가를 3~5문장으로 작성하세요.

- 매매가 적정성을 중심으로 설명
- 매물 설명의 신뢰도 분석
- 주변 실거래가 대비 가격 판단
- 마지막에 매수 시 주의사항/조언 한 줄 추가

한국어로, 친절하지만 전문적인 톤으로 작성하세요."""

EVALUATION_PROMPT_MONTHLY = """당신은 부동산 월세 전문 분석가입니다. 아래 분석 결과를 바탕으로 일반인이 이해할 수 있는 종합 평가를 3~5문장으로 작성하세요.

- 월세/보증금 적정성을 중심으로 설명
- 매물 설명의 신뢰도 분석
- 보증금 규모에 대한 안전도 언급
- 마지막에 월세 계약 시 주의사항/조언 한 줄 추가

한국어로, 친절하지만 전문적인 톤으로 작성하세요."""

EVALUATION_PROMPT_JEONSE = """당신은 부동산 전세 전문 분석가입니다. 아래 분석 결과를 바탕으로 일반인이 이해할 수 있는 종합 평가를 3~5문장으로 작성하세요.

- 신뢰도 점수와 등급의 의미를 쉽게 설명
- 전세사기 위험 요소를 구체적으로 언급 (전세가율, 등기부등본)
- 시세 비교 결과를 반영
- 보증보험 가입 가능성 언급
- 마지막에 전세 계약 시 반드시 해야 할 조언 한 줄 추가

한국어로, 친절하지만 전문적인 톤으로 작성하세요."""

REPORT_PROMPT_SALE = """당신은 부동산 매매 전문 분석가입니다.
아래 분석 데이터를 바탕으로 **매매 분석 리포트**를 JSON 배열로 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "title": "섹션 제목",
    "icon": "이모지 1개",
    "content": "2~4문장의 상세 분석 내용. 수치를 근거로 명확하게 작성.",
    "verdict": "한 줄 판정"
  }
]

아래 섹션을 순서대로 포함하세요:
1. **종합 판단** — 이 매물의 매매가가 적정한지, 주의사항이 있는지 총평 (icon: 📋)
2. **시세 분석** — 주변 실거래 시세와 비교한 결과, 적정가인지 분석 (icon: 💰)
3. **매물 텍스트 신뢰도** — 매물 설명의 허위/과장 여부 분석 (icon: 📝)
4. **매수 실행 가이드** — 매매 계약 전 반드시 해야 할 일 2~3가지 (등기부등본 열람, 실거래가 확인, 현장 방문 등) (icon: ✅)

한국어로, 전문적이지만 친절한 톤으로 작성하세요. 데이터에 없는 내용은 추측하지 마세요."""

REPORT_PROMPT_MONTHLY = """당신은 부동산 월세 전문 분석가입니다.
아래 분석 데이터를 바탕으로 **월세 분석 리포트**를 JSON 배열로 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "title": "섹션 제목",
    "icon": "이모지 1개",
    "content": "2~4문장의 상세 분석 내용. 수치를 근거로 명확하게 작성.",
    "verdict": "한 줄 판정"
  }
]

아래 섹션을 순서대로 포함하세요:
1. **종합 판단** — 이 월세 매물이 적정한지, 주의사항이 있는지 총평 (icon: 📋)
2. **시세 분석** — 주변 월세 시세와 비교한 결과, 적정 수준인지 분석 (icon: 💰)
3. **매물 텍스트 신뢰도** — 매물 설명의 허위/과장 여부 분석 (icon: 📝)
4. **보증금 안전도** — 보증금 규모가 적절한지, 보증금 보호를 위한 조언 (등기부등본 확인, 확정일자 등) (icon: 🛡️)
5. **계약 실행 가이드** — 월세 계약 전 반드시 해야 할 일 2~3가지 (icon: ✅)

한국어로, 전문적이지만 친절한 톤으로 작성하세요. 데이터에 없는 내용은 추측하지 마세요."""

REPORT_PROMPT_JEONSE = """당신은 부동산 전세 전문 분석가이자 법률 자문가입니다.
아래 분석 데이터를 바탕으로 **전세 분석 리포트**를 JSON 배열로 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "title": "섹션 제목",
    "icon": "이모지 1개",
    "content": "2~4문장의 상세 분석 내용. 수치를 근거로 명확하게 작성.",
    "verdict": "한 줄 판정"
  }
]

아래 섹션을 순서대로 포함하세요:
1. **종합 판단** — 이 전세 매물이 안전한지, 주의가 필요한지 총평 (icon: 📋)
2. **시세 분석** — 주변 실거래 시세와 비교한 결과, 적정가인지 분석 (icon: 💰)
3. **매물 텍스트 신뢰도** — 매물 설명의 허위/과장 여부 분석 (icon: 📝)
4. **등기부등본 분석** — 근저당, 압류, 신탁 등 권리관계 위험도 (등기 정보가 없으면 "등기부등본 미입력" 경고) (icon: 📄)
5. **전세 안전도** — 전세가율, 깡통전세 위험, 보증보험 가입 가능성 (icon: 🛡️)
6. **계약 실행 가이드** — 전세 계약 전 반드시 해야 할 일 2~3가지를 구체적으로 (icon: ✅)

한국어로, 전문적이지만 친절한 톤으로 작성하세요. 데이터에 없는 내용은 추측하지 마세요."""

EVAL_PROMPTS = {
    ListingType.SALE: EVALUATION_PROMPT_SALE,
    ListingType.MONTHLY: EVALUATION_PROMPT_MONTHLY,
    ListingType.JEONSE: EVALUATION_PROMPT_JEONSE,
}

REPORT_PROMPTS = {
    ListingType.SALE: REPORT_PROMPT_SALE,
    ListingType.MONTHLY: REPORT_PROMPT_MONTHLY,
    ListingType.JEONSE: REPORT_PROMPT_JEONSE,
}


class ReportGenerator:
    """분석 오케스트레이터 — 매물 유형별 맞춤 분석."""

    def __init__(self) -> None:
        self._llm = LLMService()
        self._real_estate = RealEstateAPIService()

    async def generate(self, req: ListingAnalysisRequest) -> AnalysisReport:
        text_analyzer = TextAnalyzer(self._llm)
        market_comparator = MarketComparator(self._real_estate)

        combined_task = text_analyzer.analyze_combined(req.listing_text)
        market_task = market_comparator.compare(
            req.address, req.area_sqm, req.deposit,
            listing_type=req.listing_type,
            property_type=req.property_type,
            building_name=req.building_name,
        )

        from app.models.schemas import TextAnalysisResult, ExtractedInfo

        results = await asyncio.gather(
            combined_task, market_task, return_exceptions=True,
        )

        if isinstance(results[0], Exception):
            logger.warning("Text analysis failed: %s", results[0])
            text_result = TextAnalysisResult(analyzed=False)
            text_risk = "normal"
            extracted_info = ExtractedInfo()
        else:
            text_result, text_risk, extracted_info = results[0]

        if isinstance(results[1], Exception):
            logger.warning("Market comparison failed: %s", results[1])
            market_comparison = MarketComparison()
        else:
            market_comparison = results[1]

        text_score = self._compute_text_score(text_result)
        market_score = self._compute_market_score(market_comparison)

        jeonse_risk = None
        location_verification = None
        nearby_facilities = None

        parallel_tasks: list = []

        if req.listing_type == ListingType.JEONSE:
            registry_text = None
            registry_data = None
            if req.registry and req.registry.raw_text:
                registry_text = req.registry.raw_text
            if req.registry and (req.registry.owner or req.registry.mortgage is not None):
                registry_data = RegistryAnalysis(
                    owner=req.registry.owner,
                    mortgage=req.registry.mortgage or 0,
                    seizure=req.registry.seizure,
                    trust=req.registry.trust,
                )

            sale_price = market_comparison.avg_sale_price
            jeonse_analyzer = JeonseAnalyzer(self._llm)
            is_metro = any(k in req.address for k in ("서울", "경기", "인천"))
            parallel_tasks.append(("jeonse", jeonse_analyzer.analyze(
                deposit=req.deposit,
                market_price=sale_price,
                registry_text=registry_text,
                registry_data=registry_data,
                text_risk_level=text_risk,
                property_type=req.property_type,
                is_metro=is_metro,
            )))

        parallel_tasks.append(("location", self._analyze_location(
            req.address, extracted_info.location_claims, req.listing_text,
        )))

        if parallel_tasks:
            task_results = await asyncio.gather(
                *[t[1] for t in parallel_tasks],
                return_exceptions=True,
            )
            for (name, _), result in zip(parallel_tasks, task_results):
                if isinstance(result, Exception):
                    logger.warning("%s failed: %s", name, result)
                elif name == "jeonse":
                    jeonse_risk = result
                elif name == "location":
                    location_verification, nearby_facilities = result

        reliability = calculate_reliability_score(
            text_score,
            market_score,
            jeonse_risk.risk_score if jeonse_risk else None,
        )
        grade = score_to_grade(100 - reliability)

        summary_data = self._build_summary(
            req, reliability, grade.value,
            text_result, market_comparison, jeonse_risk,
            listing_text=req.listing_text,
            location_verification=location_verification,
        )

        eval_prompt = EVAL_PROMPTS.get(req.listing_type, EVALUATION_PROMPT_JEONSE)
        report_prompt = REPORT_PROMPTS.get(req.listing_type, REPORT_PROMPT_JEONSE)

        eval_results = await asyncio.gather(
            self._generate_evaluation(summary_data, eval_prompt),
            self._generate_detailed_report(summary_data, report_prompt),
            return_exceptions=True,
        )
        evaluation = eval_results[0] if isinstance(eval_results[0], str) else ""
        ai_report = eval_results[1] if isinstance(eval_results[1], list) else []

        return AnalysisReport(
            listing_type=req.listing_type,
            reliability_score=reliability,
            reliability_grade=grade,
            evaluation=evaluation,
            ai_report=ai_report,
            text_analysis=text_result,
            extracted_info=extracted_info,
            market_comparison=market_comparison,
            location_verification=location_verification,
            nearby_facilities=nearby_facilities,
            jeonse_risk=jeonse_risk,
        )

    @staticmethod
    async def _analyze_location(
        address: str, claims: list[str], listing_text: str,
    ) -> tuple[LocationVerification | None, NearbyFacilities | None]:
        kakao = KakaoMapService()
        geo = await kakao.geocode(address)
        if not geo or not geo.lat or not geo.lng:
            return LocationVerification(), NearbyFacilities()

        verifier = LocationVerifier(kakao)
        has_claims = bool(claims) or bool(listing_text and listing_text.strip())

        tasks = []
        task_names = []

        if has_claims:
            tasks.append(verifier.verify(geo.lat, geo.lng, claims, listing_text))
            task_names.append("verify")

        tasks.append(verifier.search_nearby(geo.lat, geo.lng))
        task_names.append("nearby")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        loc_ver = None
        nearby = None
        for name, res in zip(task_names, results):
            if isinstance(res, Exception):
                logger.warning("Location %s failed: %s", name, res)
                continue
            if name == "verify":
                loc_ver = res
            elif name == "nearby":
                nearby = res

        return loc_ver, nearby

    @staticmethod
    def _build_summary(req, score, grade, text_result, market, jeonse, listing_text: str = "", location_verification=None) -> str:
        parts = [
            f"매물 유형: {req.listing_type.value} ({req.property_type.value})",
            f"주소: {req.address}",
        ]

        if req.listing_type == ListingType.MONTHLY:
            parts.append(f"보증금: {req.deposit:,.0f}만원, 월세: {req.monthly_rent or 0:,.0f}만원, 면적: {req.area_sqm}㎡")
        elif req.listing_type == ListingType.SALE:
            parts.append(f"매매가: {req.deposit:,.0f}만원, 면적: {req.area_sqm}㎡")
        else:
            parts.append(f"전세 보증금: {req.deposit:,.0f}만원, 면적: {req.area_sqm}㎡")

        parts.append(f"신뢰도 점수: {score}/100 (등급: {grade})")

        if text_result.suspicious_expressions:
            exprs = ", ".join(f'"{e.text}"({e.category.value})' for e in text_result.suspicious_expressions[:5])
            parts.append(f"의심 표현: {exprs}")
        else:
            parts.append("의심 표현: 없음")

        if market.avg_market_price:
            parts.append(f"주변 시세: {market.avg_market_price:,.0f}만원 ({market.data_scope}, {market.data_count}건)")
            parts.append(f"시세 편차: {market.deviation_rate}%, 판정: {market.assessment}")
        else:
            parts.append("시세 데이터: 조회 불가")

        if market.avg_sale_price:
            parts.append(f"매매 평균가: {market.avg_sale_price:,.0f}만원")

        if req.listing_type == ListingType.JEONSE:
            if req.registry:
                reg_parts = []
                if req.registry.owner:
                    reg_parts.append(f"소유자: {req.registry.owner}")
                if req.registry.mortgage:
                    reg_parts.append(f"근저당: {req.registry.mortgage:,.0f}만원")
                if req.registry.seizure:
                    reg_parts.append("압류/가압류: 있음")
                if req.registry.trust:
                    reg_parts.append("신탁등기: 있음")
                parts.append(f"등기부등본: {', '.join(reg_parts) if reg_parts else '데이터 있음'}")
            else:
                parts.append("등기부등본: 미입력")

            if jeonse:
                parts.append(f"전세가율: {jeonse.jeonse_rate}%, 위험점수: {jeonse.risk_score}/100")
                if jeonse.risk_factors:
                    parts.append(f"위험요소: {', '.join(jeonse.risk_factors[:5])}")
                if jeonse.insurance_check:
                    ins = jeonse.insurance_check
                    parts.append(f"전세보증보험: {'가입 가능' if ins.eligible else '가입 제한'} — {ins.verdict}")

        elif req.listing_type == ListingType.MONTHLY and req.deposit > 0:
            parts.append(f"보증금 규모: {req.deposit:,.0f}만원 — 확정일자/전입신고로 보호 필요")

        if location_verification and location_verification.claims:
            loc_lines = ["\n--- 위치 주장 검증 결과 ---"]
            for c in location_verification.claims:
                walk = f"도보 약 {c.actual_walk_min}분" if c.actual_walk_min else ""
                dist = f"{c.actual_distance_m}m" if c.actual_distance_m else ""
                name = c.nearest_name or ""
                loc_lines.append(
                    f"• \"{c.claim}\" → {c.verdict} ({name}, {dist}, {walk})"
                )
            parts.append("\n".join(loc_lines))

        if listing_text and listing_text.strip():
            truncated = listing_text.strip()[:500]
            parts.append(f"\n--- 매물 설명 원문 ---\n{truncated}")

        return "\n".join(parts)

    async def _generate_evaluation(self, summary_data: str, prompt: str) -> str:
        try:
            return await self._llm.chat(prompt, summary_data, temperature=0.4)
        except Exception as e:
            logger.warning("Evaluation generation failed: %s", e)
            return ""

    async def _generate_detailed_report(self, summary_data: str, prompt: str) -> list[AiReportSection]:
        try:
            raw = await self._llm.chat_json(prompt, summary_data, temperature=0.3)
            sections_data = raw if isinstance(raw, list) else raw.get("sections", raw.get("report", []))
            if not isinstance(sections_data, list):
                return []
            return [
                AiReportSection(
                    title=s.get("title", ""),
                    icon=s.get("icon", ""),
                    content=s.get("content", ""),
                    verdict=s.get("verdict", ""),
                )
                for s in sections_data
                if isinstance(s, dict) and s.get("title")
            ]
        except Exception as e:
            logger.warning("Detailed report generation failed: %s", e)
            return []

    @staticmethod
    def _compute_text_score(result: TextAnalysisResult) -> float:
        if not result.suspicious_expressions:
            return 100
        penalty = sum(
            {"HIGH": 25, "MEDIUM": 15, "LOW": 5}.get(e.severity.value, 5)
            for e in result.suspicious_expressions
        )
        return max(0, 100 - penalty)

    @staticmethod
    def _compute_market_score(comparison: MarketComparison) -> float:
        if comparison.deviation_rate is None:
            return 70
        abs_dev = abs(comparison.deviation_rate)
        if abs_dev <= 5:
            return 100
        if abs_dev <= 10:
            return 90
        if abs_dev <= 15:
            return 75
        if abs_dev <= 25:
            return 55
        return 30
