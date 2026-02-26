"""전세 위험도 분석 모듈.

위험도 산정 기준:
- 총 부담률 = (추정실채무액 + 보증금) / 매매시세
  → 채권최고액(근저당설정액)은 실제 대출금의 약 120%이므로 ×0.83 보정
  → 100% 초과 시 확정적 깡통전세
- 경매안전율 = 총 부담 / (매매시세 × 예상 낙찰가율)
  → 물건 유형·지역별 경매 통계 기반 낙찰가율 적용
  → 100% 초과 시 경매에서 보증금 전액 회수 불가능

참고 자료:
[1] 한국주택금융공사(HF), "전세 레버리지 리스크 추정" (2023)
[2] 국토연구원(KRIHS), "전세사기 방지를 위한 제도개선 방안" (2023)
[3] HUG 주택도시보증공사, "전세보증금반환보증 인수기준" (2025 개정)
[4] 금융위원회, "주택담보대출 담보인정비율(LTV) 산정기준"
[5] 법원경매 낙찰가율 통계 (2024~2025)
"""

import logging

from app.models.schemas import (
    JeonseRisk,
    InsuranceCheck,
    RegistryAnalysis,
    RiskGrade,
    PropertyType,
)
from app.services.llm_service import LLMService
from app.utils.scoring import (
    calculate_jeonse_risk_score,
    score_to_grade,
    estimate_actual_debt,
    get_auction_rate,
    calculate_total_burden_ratio,
    calculate_auction_safety,
)

logger = logging.getLogger(__name__)

REGISTRY_PROMPT = """당신은 등기부등본 분석 전문가입니다.
등기부등본 텍스트에서 위험 요소를 분석하여 JSON으로 반환하세요.

반드시 아래 JSON 형식으로 응답하세요:
{
  "owner": "소유자 이름",
  "mortgage": 근저당 금액(만원 단위, 숫자만),
  "seizure": 압류/가압류 존재 여부(true/false),
  "trust": 신탁등기 존재 여부(true/false),
  "risk_factors": ["발견된 위험 요소 목록"]
}
"""

PROPERTY_TYPE_LABELS: dict[PropertyType, str] = {
    PropertyType.APT: "아파트",
    PropertyType.OFFICETEL: "오피스텔",
    PropertyType.MULTIUNIT: "연립다세대",
    PropertyType.HOUSE: "단독다가구",
}

SAFETY_CHECKLIST = [
    "등기부등본 발급일이 최근 1주일 이내인지 확인",
    "소유자와 임대인이 동일인인지 확인 (신분증 대조)",
    "총 부담률((채무+보증금)/매매가)이 80% 이하인지 확인",
    "전세보증보험 가입이 가능한 매물인지 확인",
    "전세보증금반환보증(HUG/SGI) 가입 여부 확인",
    "임대인의 세금 체납 여부 확인 (국세·지방세 완납증명)",
    "확정일자를 반드시 받을 것",
    "전입신고를 계약일 당일 완료할 것",
]


class JeonseAnalyzer:
    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def analyze(
        self,
        deposit: float,
        market_price: float | None,
        registry_text: str | None = None,
        registry_data: RegistryAnalysis | None = None,
        text_risk_level: str = "normal",
        property_type: PropertyType = PropertyType.APT,
        is_metro: bool = True,
    ) -> JeonseRisk:
        jeonse_rate = None
        if market_price and market_price > 0:
            jeonse_rate = round((deposit / market_price) * 100, 1)

        registry = registry_data
        extra_risk_factors: list[str] = []

        if registry_text and not registry:
            registry, extra_risk_factors = await self._analyze_registry(registry_text)

        prop_label = PROPERTY_TYPE_LABELS.get(property_type, "아파트")

        estimated_debt = 0.0
        if registry and registry.mortgage:
            estimated_debt = estimate_actual_debt(registry.mortgage)

        total_burden_ratio = None
        auction_recovery_risk = None

        if market_price and market_price > 0:
            total_burden_ratio = calculate_total_burden_ratio(
                estimated_debt, deposit, market_price,
            )
            auction_rate = get_auction_rate(prop_label, is_metro)
            auction_recovery_risk = calculate_auction_safety(
                estimated_debt, deposit, market_price, auction_rate,
            )

        price_deviation = None
        if market_price and market_price > 0:
            price_deviation = ((deposit - market_price) / market_price) * 100

        risk_score = calculate_jeonse_risk_score(
            jeonse_rate=jeonse_rate,
            price_deviation=price_deviation,
            total_burden_ratio=total_burden_ratio,
            auction_recovery_risk=auction_recovery_risk,
            has_seizure=registry.seizure if registry else False,
            has_trust=registry.trust if registry else False,
            text_risk_level=text_risk_level,
        )

        risk_grade = score_to_grade(risk_score)
        risk_factors = self._build_risk_factors(
            jeonse_rate=jeonse_rate,
            total_burden_ratio=total_burden_ratio,
            auction_recovery_risk=auction_recovery_risk,
            estimated_debt=estimated_debt,
            deposit=deposit,
            market_price=market_price,
            registry=registry,
            prop_label=prop_label,
            is_metro=is_metro,
            extra_factors=extra_risk_factors,
        )

        insurance = self._check_insurance(
            deposit, market_price, jeonse_rate, registry,
            total_burden_ratio, property_type, is_metro,
        )

        return JeonseRisk(
            jeonse_rate=jeonse_rate,
            total_burden_ratio=round(total_burden_ratio, 1) if total_burden_ratio else None,
            auction_recovery_risk=round(auction_recovery_risk, 1) if auction_recovery_risk else None,
            estimated_actual_debt=round(estimated_debt) if estimated_debt else None,
            risk_score=risk_score,
            risk_grade=risk_grade,
            risk_factors=risk_factors,
            registry_analysis=registry,
            checklist=SAFETY_CHECKLIST,
            insurance_check=insurance,
        )

    @staticmethod
    def _build_risk_factors(
        *,
        jeonse_rate: float | None,
        total_burden_ratio: float | None,
        auction_recovery_risk: float | None,
        estimated_debt: float,
        deposit: float,
        market_price: float | None,
        registry: RegistryAnalysis | None,
        prop_label: str,
        is_metro: bool,
        extra_factors: list[str],
    ) -> list[str]:
        factors: list[str] = []

        if jeonse_rate is not None:
            if jeonse_rate >= 90:
                factors.append(
                    f"전세가율 {jeonse_rate}% — 매매가 대비 전세가 비율이 매우 높아 "
                    "깡통전세 위험이 큽니다 (한국부동산원: 90% 이상 고위험)"
                )
            elif jeonse_rate >= 80:
                factors.append(
                    f"전세가율 {jeonse_rate}% — 매매가 대비 전세가가 높은 편입니다 "
                    "(HUG: 70% 초과 시 보증료 할증 적용)"
                )
            elif jeonse_rate >= 70:
                factors.append(
                    f"전세가율 {jeonse_rate}% — 주의가 필요한 수준입니다 "
                    "(HUG 보증료 차등 기준: 70%)"
                )

        if total_burden_ratio is not None and registry and registry.mortgage:
            mortgage_display = f"{registry.mortgage:,.0f}만원"
            debt_display = f"{estimated_debt:,.0f}만원"
            if total_burden_ratio >= 100:
                factors.append(
                    f"총 부담률 {total_burden_ratio:.0f}% — 깡통전세 상태입니다. "
                    f"채권최고액 {mortgage_display}(추정실채무 {debt_display}) + "
                    f"보증금이 매매가를 초과합니다"
                )
            elif total_burden_ratio >= 90:
                factors.append(
                    f"총 부담률 {total_burden_ratio:.0f}% — 깡통전세에 근접합니다. "
                    f"채권최고액 {mortgage_display}(추정실채무 {debt_display})"
                )
            elif total_burden_ratio >= 80:
                factors.append(
                    f"총 부담률 {total_burden_ratio:.0f}% — 다소 높은 편입니다. "
                    f"채권최고액 {mortgage_display}(추정실채무 {debt_display}) "
                    "(금융위 안전 기준: LTV 85% 이내)"
                )
            elif total_burden_ratio >= 70:
                factors.append(
                    f"총 부담률 {total_burden_ratio:.0f}% — 양호한 편이나 모니터링이 필요합니다"
                )

        if auction_recovery_risk is not None and auction_recovery_risk >= 100:
            area_label = "수도권" if is_metro else "지방"
            factors.append(
                f"경매안전율 {auction_recovery_risk:.0f}% — 경매 시 보증금 전액 회수가 "
                f"어렵습니다 ({area_label} {prop_label} 평균 낙찰가율 기준)"
            )

        if registry:
            if registry.seizure:
                factors.append("압류/가압류 등기 존재 — 임대인의 채무 불이행 이력을 나타냅니다")
            if registry.trust:
                factors.append(
                    "신탁등기 설정됨 — 수탁자(신탁회사) 동의 없이 체결한 "
                    "전세계약은 보호받지 못할 수 있습니다"
                )

        factors.extend(extra_factors)
        return factors

    @staticmethod
    def _check_insurance(
        deposit: float,
        market_price: float | None,
        jeonse_rate: float | None,
        registry: RegistryAnalysis | None,
        total_burden_ratio: float | None,
        property_type: PropertyType = PropertyType.APT,
        is_metro: bool = True,
    ) -> InsuranceCheck:
        """HUG 전세보증금반환보증 가입 가능성 사전 진단.

        기준: HUG 인수기준 (2025년 개정).
        """
        reasons: list[str] = []
        blockers: list[str] = []
        tips: list[str] = []

        deposit_limit = 70000 if is_metro else 50000
        deposit_limit_label = "7억" if is_metro else "5억"
        area_label = "수도권" if is_metro else "비수도권"

        if deposit > deposit_limit:
            blockers.append(
                f"보증금 {deposit:,.0f}만원이 HUG 한도"
                f"({area_label} {deposit_limit_label})를 초과합니다"
            )
        else:
            reasons.append(
                f"보증금이 HUG 한도({area_label} {deposit_limit_label}) 이내입니다"
            )

        is_apt = property_type in (PropertyType.APT, PropertyType.OFFICETEL)
        rate_limit = 126 if is_apt else 100
        rate_label = "126%" if is_apt else "100%"

        if jeonse_rate is not None:
            if jeonse_rate <= rate_limit:
                reasons.append(
                    f"전세가율 {jeonse_rate}%로 HUG 기준"
                    f"(공시가 {rate_label}) 이내입니다"
                )
            else:
                blockers.append(
                    f"전세가율 {jeonse_rate}%로 HUG 기준"
                    f"(공시가 {rate_label})을 초과합니다"
                )
        elif market_price is None:
            tips.append(
                "매매 시세를 확인할 수 없어 전세가율 기준 판정이 제한됩니다"
            )

        if registry:
            if registry.seizure:
                blockers.append(
                    "압류/가압류가 있으면 전세보증보험 가입이 불가능합니다"
                )
            if registry.trust:
                blockers.append(
                    "신탁등기가 있으면 수탁자 동의서가 필요하며 "
                    "가입이 제한될 수 있습니다"
                )
            if total_burden_ratio is not None and total_burden_ratio > 90:
                blockers.append(
                    f"총 부담률 {total_burden_ratio:.0f}%로 HUG 담보인정비율 기준"
                    "(90%)을 초과합니다"
                )
            elif total_burden_ratio is not None and total_burden_ratio <= 90:
                reasons.append(
                    f"총 부담률 {total_burden_ratio:.0f}%로 HUG 담보인정비율 기준"
                    "(90%) 이내입니다"
                )

        eligible = len(blockers) == 0 and len(reasons) > 0

        if eligible:
            verdict = "전세보증보험(HUG) 가입 가능성이 높습니다"
            tips.append(
                "실제 가입 시 HUG 안심전세앱 또는 은행을 통해 정식 심사를 받으세요"
            )
            tips.append(
                "임대인의 국세/지방세 체납 여부도 확인이 필요합니다"
            )
        elif blockers:
            verdict = "전세보증보험 가입이 어려울 수 있습니다"
            tips.append(
                "SGI서울보증 등 다른 보증기관의 조건도 확인해보세요"
            )
            tips.append(
                "보증금을 낮추거나, 임대인에게 근저당 말소를 요청하는 방법을 고려하세요"
            )
        else:
            verdict = "추가 정보가 필요합니다"
            tips.append(
                "등기부등본 정보를 입력하면 더 정확한 진단이 가능합니다"
            )

        return InsuranceCheck(
            eligible=eligible,
            verdict=verdict,
            reasons=reasons + blockers,
            tips=tips,
        )

    async def _analyze_registry(
        self, registry_text: str
    ) -> tuple[RegistryAnalysis, list[str]]:
        data = await self._llm.chat_json(
            REGISTRY_PROMPT,
            f"다음 등기부등본을 분석해주세요:\n\n{registry_text}",
        )

        registry = RegistryAnalysis(
            owner=data.get("owner"),
            mortgage=data.get("mortgage", 0),
            seizure=data.get("seizure", False),
            trust=data.get("trust", False),
        )
        risk_factors = data.get("risk_factors", [])
        return registry, risk_factors
