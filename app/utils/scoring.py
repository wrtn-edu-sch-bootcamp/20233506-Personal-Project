"""전세 위험도 점수 산출 모듈.

참고 자료 및 근거:
- 한국주택금융공사(HF), "전세 레버리지 리스크 추정" (2023)
- 국토연구원(KRIHS), "전세사기 방지를 위한 제도개선 방안" (2023)
- HUG 주택도시보증공사, "전세보증금반환보증 인수기준" (2025 개정)
- 금융위원회, "주택담보대출 담보인정비율(LTV) 산정기준"
- 법원경매 낙찰가율 통계 (2024~2025, 지지옥션/대법원)
"""

from app.models.schemas import RiskGrade

MORTGAGE_DISCOUNT = 0.83
"""채권최고액 → 추정실채무액 보정계수.
근저당 설정 시 채권최고액은 실대출금의 약 120%로 설정되는 것이 관행.
따라서 추정실채무액 = 채권최고액 × (1/1.2) ≈ 0.83.
"""

AUCTION_RATES: dict[tuple[str, bool], float] = {
    ("아파트", True): 0.90,
    ("아파트", False): 0.80,
    ("오피스텔", True): 0.85,
    ("오피스텔", False): 0.75,
    ("연립다세대", True): 0.70,
    ("연립다세대", False): 0.60,
    ("단독다가구", True): 0.65,
    ("단독다가구", False): 0.55,
}
"""물건 유형 × 수도권 여부별 예상 경매 낙찰가율.
근거: 2024~2025 법원경매 통계.
- 서울 아파트 92~97%, 수도권 85~90% → 보수적 90%
- 빌라/연립: 전세사기 여파로 60~70%
- 단독/다가구: 55~70%
"""


def estimate_actual_debt(mortgage: float) -> float:
    """채권최고액(근저당설정액)에서 추정 실제 채무액 계산."""
    return mortgage * MORTGAGE_DISCOUNT


def get_auction_rate(property_type: str, is_metro: bool) -> float:
    return AUCTION_RATES.get((property_type, is_metro), 0.75)


def calculate_total_burden_ratio(
    estimated_debt: float,
    deposit: float,
    market_price: float,
) -> float | None:
    """총 부담률 = (추정실채무액 + 전세보증금) / 매매시세 × 100.

    깡통전세 판단의 핵심 지표.
    참고: 금융위원회 LTV 산정기준, HUG 인수기준.
    """
    if not market_price or market_price <= 0:
        return None
    return ((estimated_debt + deposit) / market_price) * 100


def calculate_auction_safety(
    estimated_debt: float,
    deposit: float,
    market_price: float,
    auction_rate: float,
) -> float | None:
    """경매안전율 = (추정실채무액 + 전세보증금) / (매매시세 × 낙찰가율) × 100.

    100% 초과 시 경매에서 보증금 전액 회수 불가.
    참고: 법원경매 낙찰가율 통계, 국토연구원 연구보고서.
    """
    if not market_price or market_price <= 0 or auction_rate <= 0:
        return None
    auction_value = market_price * auction_rate
    return ((estimated_debt + deposit) / auction_value) * 100


def calculate_jeonse_risk_score(
    jeonse_rate: float | None = None,
    price_deviation: float | None = None,
    total_burden_ratio: float | None = None,
    auction_recovery_risk: float | None = None,
    has_seizure: bool = False,
    has_trust: bool = False,
    text_risk_level: str = "normal",
) -> int:
    """전세 위험도 점수 산출 (0~100, 높을수록 위험).

    점수 배분 설계 근거:
    ┌───────────────────────┬──────────┬────────────────────────────────┐
    │ 항목                  │ 최대배점 │ 근거                           │
    ├───────────────────────┼──────────┼────────────────────────────────┤
    │ 전세가율              │ 35       │ 한국부동산원/HUG 기준          │
    │ 총 부담률(깡통전세)   │ 35       │ 금융위 LTV 기준/국토연구원     │
    │ 경매안전율            │ 10       │ 법원경매 통계 기반 보정        │
    │ 시세편차(저가의심)    │ 10       │ 전세사기 유형 분석             │
    │ 권리관계(압류/신탁)   │ 35       │ 등기법/판례                    │
    │ 매물텍스트 위험       │ 10       │ SafeHome 자체 분석             │
    └───────────────────────┴──────────┴────────────────────────────────┘
    ※ 개별 항목 합이 100을 초과할 수 있으나 최종 점수는 min(합계, 100).
    """
    score = 0

    # 1. 전세가율 (최대 35점)
    # HUG: 전세가율 70% 기준 보증료 차등. 한국부동산원: 90% 이상 고위험.
    if jeonse_rate is not None:
        if jeonse_rate >= 90:
            score += 35
        elif jeonse_rate >= 80:
            score += 25
        elif jeonse_rate >= 70:
            score += 15
        elif jeonse_rate >= 60:
            score += 5

    # 2. 총 부담률 — 깡통전세 핵심 지표 (최대 35점)
    # 금융위: LTV 85% 이내 안전. HUG: 담보인정비율 80→90% 기준.
    # 100% 초과 = 확정적 깡통전세.
    if total_burden_ratio is not None:
        if total_burden_ratio >= 100:
            score += 35
        elif total_burden_ratio >= 90:
            score += 25
        elif total_burden_ratio >= 80:
            score += 15
        elif total_burden_ratio >= 70:
            score += 5

    # 3. 경매안전율 초과 보정 (최대 10점)
    # 물건 유형별 낙찰가율을 반영한 실질 회수 가능성 판단.
    if auction_recovery_risk is not None and auction_recovery_risk >= 100:
        score += 10

    # 4. 시세 편차 — 저가 미끼 전세 감지 (최대 10점)
    if price_deviation is not None and price_deviation < 0:
        abs_dev = abs(price_deviation)
        if abs_dev >= 20:
            score += 10
        elif abs_dev >= 10:
            score += 5

    # 5. 권리관계 위험 (최대 35점)
    if has_seizure:
        score += 25

    if has_trust:
        score += 15

    # 6. 매물 텍스트 위험 (최대 10점)
    if text_risk_level == "suspicious":
        score += 10
    elif text_risk_level == "exaggeration":
        score += 5

    return min(score, 100)


def score_to_grade(score: float) -> RiskGrade:
    """위험 점수 → 등급 변환.

    등급 기준:
    - 0~20: 안전 — 정상적인 거래 범위
    - 21~40: 주의 — 일부 위험 요소 존재, 꼼꼼한 확인 필요
    - 41~60: 경고 — 여러 위험 요소 복합, 전문가 상담 권장
    - 61~100: 위험 — 전세사기/깡통전세 가능성 높음
    """
    if score <= 20:
        return RiskGrade.SAFE
    elif score <= 40:
        return RiskGrade.CAUTION
    elif score <= 60:
        return RiskGrade.WARNING
    else:
        return RiskGrade.DANGER


def calculate_reliability_score(
    text_score: float,
    market_score: float,
    jeonse_risk_score: float | None = None,
) -> float:
    """종합 신뢰도 점수 (0~100, 높을수록 신뢰)."""
    if jeonse_risk_score is not None:
        raw = (text_score * 0.3 + market_score * 0.3 + (100 - jeonse_risk_score) * 0.4)
    else:
        raw = (text_score * 0.5 + market_score * 0.5)
    return max(0, min(100, round(raw, 1)))
