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

COMBINED_PROMPT = """당신은 부동산 매물 텍스트 분석 전문가입니다.
매물 설명에서 (1) 허위·과장 표현 탐지와 (2) 핵심 정보 추출을 동시에 수행하세요.

## 허위·과장 탐지 카테고리
- EXAGGERATION: 과장 표현 (예: "초역세권", "풀옵션", "최고급", "황금")
- MISLEADING: 오해 유발 (예: "리모델링 완료" 실제 일부만, "신축급")
- PRICE_BAIT: 미끼 가격 (비정상적 저가로 유인)
- OMISSION: 중요 정보 누락 의심 (반지하/북향/도로변 등 미기재, 확인 필요 사항)
- NORMAL: 정상 서술

## 심각도
- HIGH: 사기 의심, 허위 가능성 높음
- MEDIUM: 과장·오해 소지, 확인 필요
- LOW: 경미한 과장이나 관행적 표현

반드시 아래 JSON 형식으로만 응답하세요:
{
  "expressions": [
    {
      "text": "원문 중 해당 표현",
      "category": "카테고리",
      "severity": "심각도",
      "reason": "왜 이 표현이 의심스러운지 구체적 설명"
    }
  ],
  "text_risk_level": "normal | exaggeration | suspicious",
  "extracted_info": {
    "price": "가격 정보 (예: '전세 3억', '월세 50/500') 또는 null",
    "area": "면적 정보 (예: '59㎡ (약 18평)') 또는 null",
    "floor": "층수 정보 (예: '5층/15층') 또는 null",
    "location_claims": ["위치 관련 주장 (역세권, 학교 근처 등)"],
    "facilities": ["시설/옵션 (에어컨, 세탁기, 풀옵션 등)"]
  }
}

주의사항:
- 짧은 텍스트라도 반드시 분석하세요. 정보가 너무 적으면 OMISSION으로 지적하세요.
- 매물 설명으로 보이지 않는 텍스트(예: 테스트, 인사말)도 그 자체로 "매물 정보 미기재"로 분석하세요.
- expressions가 없으면 빈 배열 []로 두되, 최소한 전체적 인상에 대한 1개 이상의 분석을 포함하세요."""


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
