import logging

from app.models.schemas import (
    SuspiciousExpression,
    SuspiciousCategory,
    Severity,
    TextAnalysisResult,
    ExtractedInfo,
)
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

COMBINED_PROMPT = """당신은 한국 부동산 매물 텍스트를 분석하는 전문가입니다.
매물 설명에서 (1) 허위·과장 표현 탐지와 (2) 핵심 정보 추출을 동시에 수행하세요.

## 입력 텍스트 판단
- 먼저 입력이 **부동산 매물 설명**인지 판단하세요.
- 매물 설명이 아닌 텍스트(테스트 문자, 인사말, 관계없는 내용)인 경우:
  text_risk_level을 "not_listing"으로 설정하고, expressions는 빈 배열로 두세요.

## 업계 관용 표현 (LOW 또는 무시)
다음은 한국 부동산 업계에서 **일반적으로 사용하는 관행적 표현**입니다.
이 표현들은 과장이 아니라 업계 표준 용어이므로 LOW로 분류하거나 무시하세요:
- 위치: "역세권", "초역세권", "더블역세권", "학세권", "숲세권", "역 도보 N분"
- 상태: "풀옵션", "올수리", "올리모델링", "신축급", "즉시입주", "깔끔", "탁트인 뷰"
- 일반 홍보: "급매", "실입주", "전망 좋은", "채광 좋은", "남향", "로열층"

## 실질적 위험 표현 (MEDIUM ~ HIGH)
다음에 해당할 때만 MEDIUM 이상으로 분류하세요:
- **PRICE_BAIT** (HIGH): 해당 지역 시세 대비 비현실적으로 낮은 가격 언급, "급전 필요" 등 급매 압박
- **MISLEADING** (MEDIUM~HIGH): 검증 불가능한 수익률 제시, "확정 수익", "무조건 오른다" 등
- **OMISSION** (MEDIUM): 반지하/옥탑/북향/도로변/소음 등 중요 단점을 의도적으로 누락한 징후
- **EXAGGERATION** (LOW~MEDIUM): 객관적 근거 없는 "최고급", "최상위", "유일무이" 등 극단적 수식어
- **NORMAL**: 사실에 기반한 정상적 서술

## 긍정적 요소
신뢰도를 높이는 긍정적 표현도 expressions에 포함하세요 (severity: "LOW", category: "NORMAL"):
- 구체적인 옵션/시설 명시, 정확한 면적/층수 기재, 관리비 상세 안내, 실사진 언급 등

## 심각도 기준
- **HIGH**: 사기 의심 또는 명백한 허위 (가격 조작, 존재하지 않는 시설 주장 등)
- **MEDIUM**: 오해 유발 가능, 현장 확인 권장 (애매한 표현, 과장된 수익 주장 등)
- **LOW**: 업계 관행적 표현이거나 경미한 과장 / 긍정적 신뢰 요소

반드시 아래 JSON 형식으로만 응답하세요:
{
  "expressions": [
    {
      "text": "원문 중 해당 표현",
      "category": "EXAGGERATION | MISLEADING | PRICE_BAIT | OMISSION | NORMAL",
      "severity": "HIGH | MEDIUM | LOW",
      "reason": "판단 근거를 구체적으로 설명"
    }
  ],
  "text_risk_level": "normal | exaggeration | suspicious | not_listing",
  "extracted_info": {
    "price": "가격 정보 (예: '전세 3억', '월세 50/500') 또는 null",
    "area": "면적 정보 (예: '59㎡ (약 18평)') 또는 null",
    "floor": "층수 정보 (예: '5층/15층') 또는 null",
    "location_claims": ["위치 관련 주장"],
    "facilities": ["시설/옵션 목록"]
  }
}"""


class TextAnalyzer:
    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def analyze(self, listing_text: str) -> tuple[TextAnalysisResult, str]:
        """Returns (TextAnalysisResult, text_risk_level)."""
        data = await self._llm.chat_json(
            COMBINED_PROMPT,
            f"다음 매물 설명을 분석해주세요:\n\n{listing_text}",
        )

        expressions = []
        for item in data.get("expressions", []):
            try:
                expressions.append(
                    SuspiciousExpression(
                        text=item["text"],
                        category=SuspiciousCategory(item["category"]),
                        severity=Severity(item["severity"]),
                        reason=item["reason"],
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed expression: %s", e)

        risk_level = data.get("text_risk_level", "normal")
        return TextAnalysisResult(suspicious_expressions=expressions), risk_level

    def extract_info_from_data(self, data: dict) -> ExtractedInfo:
        info = data.get("extracted_info", {})
        if not isinstance(info, dict):
            return ExtractedInfo()
        return ExtractedInfo(
            price=info.get("price"),
            area=info.get("area"),
            floor=info.get("floor"),
            location_claims=info.get("location_claims", []),
            facilities=info.get("facilities", []),
        )

    async def analyze_combined(self, listing_text: str) -> tuple[TextAnalysisResult, str, ExtractedInfo]:
        """Combined analysis: text analysis + info extraction in one LLM call."""
        data = await self._llm.chat_json(
            COMBINED_PROMPT,
            f"다음 매물 설명을 분석해주세요:\n\n{listing_text}",
        )

        expressions = []
        for item in data.get("expressions", []):
            try:
                expressions.append(
                    SuspiciousExpression(
                        text=item["text"],
                        category=SuspiciousCategory(item["category"]),
                        severity=Severity(item["severity"]),
                        reason=item["reason"],
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed expression: %s", e)

        risk_level = data.get("text_risk_level", "normal")
        extracted = self.extract_info_from_data(data)

        return TextAnalysisResult(suspicious_expressions=expressions), risk_level, extracted
