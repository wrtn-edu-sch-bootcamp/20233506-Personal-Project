import logging

from app.models.schemas import ExtractedInfo
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 부동산 매물 텍스트에서 핵심 정보를 추출하는 전문가입니다.
텍스트에서 구조화된 정보를 추출하여 JSON으로 반환하세요.

반드시 아래 JSON 형식으로 응답하세요:
{
  "price": "가격 정보 (예: '전세 3억', '월세 50/500')",
  "area": "면적 정보 (예: '59㎡ (약 18평)')",
  "floor": "층수 정보 (예: '5층/15층')",
  "location_claims": ["위치 관련 주장들 (예: '역세권', '학교 근처')"],
  "facilities": ["시설/옵션 목록 (예: '에어컨', '세탁기', '풀옵션')"]
}
"""


class InfoExtractor:
    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def extract(self, listing_text: str) -> ExtractedInfo:
        data = await self._llm.chat_json(
            SYSTEM_PROMPT,
            f"다음 매물 설명에서 핵심 정보를 추출해주세요:\n\n{listing_text}",
        )

        return ExtractedInfo(
            price=data.get("price"),
            area=data.get("area"),
            floor=data.get("floor"),
            location_claims=data.get("location_claims", []),
            facilities=data.get("facilities", []),
        )
