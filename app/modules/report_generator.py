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

EVALUATION_PROMPT_SALE = """당신은 10년 경력의 부동산 매매 전문 분석가입니다. 아래 분석 데이터를 바탕으로 일반인이 이해할 수 있는 종합 평가를 6~10문장으로 작성하세요.

반드시 포함할 내용:
- 이 매물의 매매가가 주변 실거래가 대비 어느 수준인지 구체적 수치와 함께 설명
- 시세 편차가 의미하는 바를 일반인도 이해할 수 있게 풀어서 설명 (예: "주변 평균 대비 약 5% 저렴한 수준으로, 시장 정상 범위 내입니다")
- 매물 설명 텍스트의 신뢰도 — 과장/허위가 있었다면 어떤 부분이 왜 문제인지
- 위치 주장 검증 결과가 있다면 언급 (실제 거리 vs 주장)
- 최근 시세 추이 (상승/하락/안정)가 매수 타이밍에 어떤 의미인지
- 이 매물의 장점과 단점을 균형 있게 언급
- 마지막에 매수 전 반드시 해야 할 실행 조언 1~2줄

톤: 친근하지만 전문적, 데이터 기반으로 객관적. 한국어로 작성."""

EVALUATION_PROMPT_MONTHLY = """당신은 10년 경력의 부동산 월세 전문 분석가입니다. 아래 분석 데이터를 바탕으로 일반인이 이해할 수 있는 종합 평가를 6~10문장으로 작성하세요.

반드시 포함할 내용:
- 이 월세 매물의 보증금/월세가 주변 시세 대비 어느 수준인지 구체적 수치와 함께 설명
- 보증금 규모의 안전성 — 보증금이 크다면 확정일자/전입신고의 중요성 강조
- 매물 설명 텍스트의 신뢰도 — 과장/허위가 있었다면 구체적으로 언급
- 위치 주장 검증 결과가 있다면 언급
- 보증금 대비 월세 비율이 적정한지 (전환율 기준으로 판단)
- 이 매물의 장점과 단점을 균형 있게 언급
- 마지막에 월세 계약 전 반드시 해야 할 실행 조언 1~2줄

톤: 친근하지만 전문적, 데이터 기반으로 객관적. 한국어로 작성."""

EVALUATION_PROMPT_JEONSE = """당신은 10년 경력의 부동산 전세 전문 분석가이자 전세사기 예방 전문가입니다. 아래 분석 데이터를 바탕으로 일반인이 이해할 수 있는 종합 평가를 8~12문장으로 작성하세요.

반드시 포함할 내용:
- 신뢰도 점수와 등급이 의미하는 바를 쉽게 풀어서 설명
- 전세가율 수치와 위험 수준 설명 (60% 이하 안전, 80% 이상 위험한 이유)
- 등기부등본 분석 결과: 근저당 금액이 매매가 대비 어느 정도인지, 이것이 왜 위험/안전한지
- 압류/가압류/신탁 등기가 있다면 그것이 임차인에게 미치는 영향
- 전세보증보험 가입 가능 여부와 그 의미
- 시세 대비 전세금의 적정성
- 위치 주장 검증 결과가 있다면 언급
- 이 매물의 장점과 위험 요소를 균형 있게 언급
- 전세 계약 전 반드시 해야 할 핵심 조언 2~3줄 (등기부등본 열람, 확정일자, 전입신고, 보증보험 등)

톤: 친근하지만 전문적, 경계심을 갖되 공포를 조장하지 않게. 한국어로 작성."""

REPORT_PROMPT_SALE = """당신은 10년 경력의 부동산 매매 전문 분석가입니다.
아래 분석 데이터를 바탕으로 **매매 분석 리포트**를 JSON 배열로 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "title": "섹션 제목",
    "icon": "이모지 1개",
    "content": "5~8문장의 상세하고 구체적인 분석 내용. 반드시 수치와 근거를 포함하여 작성.",
    "verdict": "핵심 판정 한 줄"
  }
]

아래 섹션을 순서대로 포함하세요:
1. **종합 판단** — 이 매물의 전체적인 평가. 신뢰도 점수의 의미, 가격 적정성, 주요 장점/단점을 종합적으로 서술 (icon: 📋)
2. **시세 분석** — 주변 실거래가 평균과 비교한 상세 분석. 편차율이 의미하는 바, 최근 시세 추이(상승/안정/하락)가 매수 타이밍에 주는 시사점, 같은 건물/동네 거래 사례 언급 (icon: 💰)
3. **매물 텍스트 신뢰도** — 매물 설명에서 발견된 과장/허위/긍정적 요소를 구체적으로 분석. 어떤 표현이 왜 문제인지, 또는 왜 신뢰할 수 있는지 상세히 설명 (icon: 📝)
4. **위치·주변환경 분석** — 위치 주장 검증 결과(있다면), 주변 편의시설 접근성, 교통 여건 등을 종합적으로 평가 (icon: 📍)
5. **투자 관점 분석** — 이 지역의 최근 시세 흐름, 향후 가치 변동 가능성(재개발/재건축 언급이 있다면), 매매가 대비 수익성 등 투자 관점에서의 의견 (icon: 📈)
6. **매수 실행 가이드** — 매매 계약 전 반드시 해야 할 일을 단계별로 상세히 안내. ①등기부등본 열람 및 확인 포인트, ②현장 방문 시 체크사항, ③계약서 작성 시 주의사항, ④잔금 전 최종 확인 등 (icon: ✅)

한국어로, 전문적이지만 친절한 톤으로 작성하세요. 데이터에 있는 수치를 적극 활용하고, 데이터에 없는 내용은 추측하지 마세요."""

REPORT_PROMPT_MONTHLY = """당신은 10년 경력의 부동산 월세 전문 분석가입니다.
아래 분석 데이터를 바탕으로 **월세 분석 리포트**를 JSON 배열로 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "title": "섹션 제목",
    "icon": "이모지 1개",
    "content": "5~8문장의 상세하고 구체적인 분석 내용. 반드시 수치와 근거를 포함하여 작성.",
    "verdict": "핵심 판정 한 줄"
  }
]

아래 섹션을 순서대로 포함하세요:
1. **종합 판단** — 이 월세 매물의 전체적인 평가. 보증금/월세 적정성, 주요 장점/단점을 종합적으로 서술 (icon: 📋)
2. **시세 분석** — 주변 월세 시세와 비교한 상세 분석. 보증금과 월세 각각의 적정성, 보증금-월세 전환율(연 4~5% 기준) 관점에서의 분석, 최근 시세 추이 (icon: 💰)
3. **매물 텍스트 신뢰도** — 매물 설명에서 발견된 과장/허위/긍정적 요소를 구체적으로 분석. 어떤 표현이 왜 문제인지, 또는 왜 신뢰할 수 있는지 (icon: 📝)
4. **위치·주변환경 분석** — 위치 주장 검증 결과(있다면), 주변 편의시설 접근성, 교통 여건 등 종합 평가 (icon: 📍)
5. **보증금 안전도** — 보증금 규모별 리스크 분석. 보증금이 클 경우 확정일자/전입신고/보증보험의 중요성, 소액임차인 최우선변제금 해당 여부 등을 구체적으로 안내 (icon: 🛡️)
6. **계약 실행 가이드** — 월세 계약 전 반드시 해야 할 일을 단계별로 안내. ①등기부등본 열람 포인트, ②전입신고와 확정일자 받는 방법, ③계약서 특약사항 체크, ④관리비/옵션 실물 확인 등 (icon: ✅)

한국어로, 전문적이지만 친절한 톤으로 작성하세요. 데이터에 있는 수치를 적극 활용하고, 데이터에 없는 내용은 추측하지 마세요."""

REPORT_PROMPT_JEONSE = """당신은 10년 경력의 부동산 전세 전문 분석가이자 전세사기 예방 법률 자문가입니다.
아래 분석 데이터를 바탕으로 **전세 분석 리포트**를 JSON 배열로 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "title": "섹션 제목",
    "icon": "이모지 1개",
    "content": "5~10문장의 상세하고 구체적인 분석 내용. 반드시 수치와 근거를 포함하여 작성.",
    "verdict": "핵심 판정 한 줄"
  }
]

아래 섹션을 순서대로 포함하세요:
1. **종합 판단** — 이 전세 매물의 전체적 안전도 평가. 신뢰도 점수와 위험 등급의 의미를 일반인도 알기 쉽게 풀어서 설명. 주요 위험 요소와 긍정적 요소를 균형 있게 서술 (icon: 📋)
2. **시세 분석** — 주변 전세 실거래가 평균과의 비교 상세 분석. 편차율의 의미, 최근 시세 추이(상승/안정/하락), 같은 건물/동네의 최근 거래 사례 언급. 시장 전세가율과 이 매물의 전세가율 비교 (icon: 💰)
3. **매물 텍스트 신뢰도** — 매물 설명에서 발견된 의심 표현, 과장, 긍정적 요소를 각각 구체적으로 분석. 부동산 업계 관용표현과 실제 위험 표현을 구분하여 설명 (icon: 📝)
4. **등기부등본 상세 분석** — 근저당 설정액이 매매가 대비 몇 %인지, 채권최고액에서 실제 대출금을 추정하는 방법(채권최고액 × 0.77~0.83), 압류/가압류가 임차인에게 미치는 법적 영향, 신탁등기의 위험성. 등기 정보가 없다면 반드시 열람해야 하는 이유를 강력히 경고 (icon: 📄)
5. **전세사기 위험도 상세** — 전세가율 수치와 위험 수준을 국토연구원 기준(60% 이하 안전, 70~80% 주의, 80% 이상 위험)으로 설명. 깡통전세 여부 판단, 경매 시 보증금 회수 가능성, 총 부담률과 경매안전율 수치의 의미를 일반인이 이해할 수 있게 풀어 설명 (icon: ⚠️)
6. **전세보증보험 진단** — HUG/SGI 전세보증보험 가입 가능 여부와 조건. 가입이 제한되는 사유가 있다면 구체적으로 명시. 보증보험의 보호 범위와 가입 방법 안내 (icon: 🛡️)
7. **위치·주변환경 분석** — 위치 주장 검증 결과(있다면), 주변 편의시설 접근성, 교통 여건 등 종합 평가 (icon: 📍)
8. **계약 실행 가이드** — 전세 계약의 전체 과정을 단계별로 상세 안내. ①계약 전: 등기부등본 열람(갑구/을구 확인 포인트), 건축물대장 확인, 집주인 본인 확인 ②계약 시: 특약사항 필수 기재 항목, 계약금 비율 ③계약 후: 전입신고+확정일자(당일!), 전세보증보험 가입, 잔금 전 등기부등본 재열람 ④입주 후: 주기적 등기변동 확인 (icon: ✅)

한국어로, 전문적이지만 친절한 톤으로 작성하세요. 데이터에 있는 수치를 적극 활용하되, 데이터에 없는 내용은 추측하지 마세요. 위험 요소는 명확히 경고하되 공포를 조장하지 마세요."""

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
            nearby_facilities=nearby_facilities,
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
    def _build_summary(
        req, score, grade, text_result, market, jeonse,
        listing_text: str = "", location_verification=None,
        nearby_facilities=None,
    ) -> str:
        parts = [
            f"매물 유형: {req.listing_type.value} ({req.property_type.value})",
            f"주소: {req.address}",
            f"건물/단지명: {req.building_name}" if req.building_name else "",
        ]

        if req.listing_type == ListingType.MONTHLY:
            parts.append(f"보증금: {req.deposit:,.0f}만원, 월세: {req.monthly_rent or 0:,.0f}만원, 면적: {req.area_sqm}㎡ (약 {req.area_sqm / 3.3058:.1f}평)")
        elif req.listing_type == ListingType.SALE:
            parts.append(f"매매가: {req.deposit:,.0f}만원, 면적: {req.area_sqm}㎡ (약 {req.area_sqm / 3.3058:.1f}평)")
        else:
            parts.append(f"전세 보증금: {req.deposit:,.0f}만원, 면적: {req.area_sqm}㎡ (약 {req.area_sqm / 3.3058:.1f}평)")

        parts.append(f"신뢰도 점수: {score}/100 (등급: {grade})")

        if text_result.suspicious_expressions:
            for e in text_result.suspicious_expressions[:8]:
                parts.append(f"  - \"{e.text}\" [{e.category.value}, {e.severity.value}]: {e.reason}")
        else:
            parts.append("의심 표현: 발견되지 않음")

        parts.append("\n--- 시세 분석 데이터 ---")
        if market.avg_market_price:
            parts.append(f"주변 시세 평균: {market.avg_market_price:,.0f}만원 ({market.data_scope}, {market.data_count}건 기준)")
            parts.append(f"시세 편차: {market.deviation_rate}%, 판정: {market.assessment}")
        else:
            parts.append("시세 데이터: 조회 불가")

        if market.avg_sale_price:
            parts.append(f"매매 평균가: {market.avg_sale_price:,.0f}만원")

        if market.price_trend:
            parts.append(f"최근 시세 추이: {market.price_trend} (최근 3개월 vs 12개월 평균 비교)")

        if market.jeonse_rate_market is not None:
            parts.append(f"시장 전세가율: {market.jeonse_rate_market}% (위험도: {market.jeonse_rate_risk})")

        if market.data_source:
            parts.append(f"데이터 출처: {market.data_source}")

        if market.recent_trades:
            parts.append(f"\n최근 실거래 사례 ({len(market.recent_trades)}건):")
            for t in market.recent_trades[:5]:
                parts.append(f"  - {t.year}.{t.month}.{t.day} {t.name or t.dong} {t.trade_type} {t.price:,.0f}만원 ({t.area_sqm}㎡, {t.floor}층)")

        if req.listing_type == ListingType.JEONSE:
            parts.append("\n--- 등기부등본 분석 ---")
            if req.registry:
                if req.registry.owner:
                    parts.append(f"소유자: {req.registry.owner}")
                if req.registry.mortgage:
                    parts.append(f"근저당 설정액: {req.registry.mortgage:,.0f}만원")
                    if market.avg_sale_price:
                        ratio = (req.registry.mortgage / market.avg_sale_price) * 100
                        parts.append(f"근저당/매매가 비율: {ratio:.1f}%")
                if req.registry.seizure:
                    parts.append("압류/가압류: 있음 (중대한 위험 요소)")
                if req.registry.trust:
                    parts.append("신탁등기: 있음 (주의 필요)")
            else:
                parts.append("등기부등본: 미입력 (반드시 열람 필요)")

            if jeonse:
                parts.append(f"\n--- 전세사기 위험도 분석 ---")
                parts.append(f"전세가율: {jeonse.jeonse_rate}%")
                parts.append(f"위험 점수: {jeonse.risk_score}/100 (등급: {jeonse.risk_grade.value})")
                if jeonse.total_burden_ratio is not None:
                    parts.append(f"총 부담률: {jeonse.total_burden_ratio:.1f}%")
                if jeonse.auction_recovery_risk is not None:
                    parts.append(f"경매안전율: {jeonse.auction_recovery_risk:.1f}%")
                if jeonse.risk_factors:
                    parts.append(f"위험 요소: {', '.join(jeonse.risk_factors)}")
                if jeonse.checklist:
                    parts.append(f"체크리스트: {', '.join(jeonse.checklist[:5])}")
                if jeonse.insurance_check:
                    ins = jeonse.insurance_check
                    parts.append(f"전세보증보험: {'가입 가능' if ins.eligible else '가입 제한'} — {ins.verdict}")
                    if ins.reasons:
                        parts.append(f"  근거: {', '.join(ins.reasons[:3])}")
                    if ins.tips:
                        parts.append(f"  가입 팁: {', '.join(ins.tips[:3])}")

        elif req.listing_type == ListingType.MONTHLY and req.deposit > 0:
            parts.append(f"\n보증금 규모: {req.deposit:,.0f}만원")
            if req.deposit >= 5000:
                parts.append("보증금이 5000만원 이상으로 확정일자/전입신고 및 보증보험 검토 권장")

        if location_verification and location_verification.claims:
            parts.append(f"\n--- 위치 주장 검증 결과 (확인됨: {location_verification.verified_count}, 과장됨: {location_verification.exaggerated_count}) ---")
            for c in location_verification.claims:
                walk = f"도보 약 {c.actual_walk_min}분" if c.actual_walk_min else ""
                dist = f"{c.actual_distance_m}m" if c.actual_distance_m else ""
                name = c.nearest_name or ""
                claimed = f"(주장: 도보 {c.claimed_walk_min}분)" if c.claimed_walk_min else ""
                parts.append(f"  • \"{c.claim}\" → {c.verdict} — {name}, {dist}, {walk} {claimed}")

        if nearby_facilities:
            fac_parts = []
            for field in ("subway", "school", "mart", "hospital", "park", "convenience"):
                items = getattr(nearby_facilities, field, [])
                if items:
                    names = ", ".join(f"{f.name}({f.distance_m}m)" for f in items[:2])
                    fac_parts.append(f"  {field}: {names}")
            if fac_parts:
                parts.append("\n--- 주변 편의시설 ---")
                parts.extend(fac_parts)

        if listing_text and listing_text.strip():
            truncated = listing_text.strip()[:800]
            parts.append(f"\n--- 매물 설명 원문 ---\n{truncated}")

        return "\n".join(p for p in parts if p)

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
