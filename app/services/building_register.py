"""건축물대장 조회 서비스 (공공데이터포털 API).

위반건축물 여부, 건물 용도, 건축년도, 구조 등을 조회하여
전세사기 위험도 분석에 활용합니다.
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from app.config import get_settings
from app.services.kakao_map_service import KakaoMapService, GeocodingResult

logger = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService"


@dataclass
class BuildingInfo:
    building_name: str = ""
    address: str = ""
    road_address: str = ""
    main_purpose: str = ""
    other_purpose: str = ""
    structure: str = ""
    roof_type: str = ""
    total_area: float = 0
    building_area: float = 0
    ground_floors: int = 0
    underground_floors: int = 0
    households: int = 0
    units: int = 0
    elevator_count: int = 0
    approval_date: str = ""
    construction_year: int = 0
    building_age: int = 0
    is_violation: bool = False
    violation_content: str = ""
    register_type: str = ""
    energy_grade: str = ""
    found: bool = False
    risk_factors: list[str] = field(default_factory=list)


class BuildingRegisterService:
    """공공데이터포털 건축물대장 API 서비스."""

    def __init__(self, kakao: KakaoMapService | None = None) -> None:
        settings = get_settings()
        self._api_key = settings.real_estate_api_key
        self._kakao = kakao or KakaoMapService()

    async def get_building_info(
        self,
        address: str,
        building_name: str = "",
    ) -> BuildingInfo:
        if not self._api_key:
            logger.warning("Building register API key not configured")
            return BuildingInfo()

        geo = await self._kakao.geocode(address if not building_name else f"{address} {building_name}")
        if not geo or not geo.lawd_cd:
            logger.info("Geocoding failed for building register: %s", address)
            return BuildingInfo()

        sigungu_cd = geo.lawd_cd
        bjdong_cd = geo.bjdong_cd
        bun = geo.main_no.zfill(4) if geo.main_no else ""
        ji = geo.sub_no.zfill(4) if geo.sub_no else "0000"

        if not bjdong_cd or not bun:
            logger.info("Missing bjdong_cd or bun for address: %s (bjdong=%s, bun=%s)", address, bjdong_cd, bun)
            return BuildingInfo()

        info = await self._query_title(sigungu_cd, bjdong_cd, bun, ji)

        if not info.found and ji != "0000":
            info = await self._query_title(sigungu_cd, bjdong_cd, bun, "0000")

        if info.found:
            info.risk_factors = self._analyze_risks(info)

        return info

    async def _query_title(
        self,
        sigungu_cd: str,
        bjdong_cd: str,
        bun: str,
        ji: str,
    ) -> BuildingInfo:
        params = {
            "serviceKey": self._api_key,
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "bun": bun,
            "ji": ji,
            "numOfRows": "5",
            "pageNo": "1",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE_URL}/getBrTitleInfo",
                    params=params,
                )
                resp.raise_for_status()
                return self._parse_title_xml(resp.text)
        except Exception as e:
            logger.warning("Building register API failed: %s", e)
            return BuildingInfo()

    def _parse_title_xml(self, xml_text: str) -> BuildingInfo:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.error("Failed to parse building register XML")
            return BuildingInfo()

        result_code = ""
        for code_elem in root.iter("resultCode"):
            result_code = (code_elem.text or "").strip()
            break

        if result_code != "00":
            return BuildingInfo()

        items = list(root.iter("item"))
        if not items:
            return BuildingInfo()

        item = items[0]
        now_year = datetime.now().year

        approval_str = (item.findtext("useAprDay") or "").strip()
        construction_year = 0
        if approval_str and len(approval_str) >= 4:
            try:
                construction_year = int(approval_str[:4])
            except ValueError:
                pass

        ground_floors = self._safe_int(item.findtext("grndFlrCnt"))
        underground_floors = self._safe_int(item.findtext("ugrndFlrCnt"))
        rider_elv = self._safe_int(item.findtext("rideUseElvtCnt"))
        emgen_elv = self._safe_int(item.findtext("emgenUseElvtCnt"))

        vltn_yn = (item.findtext("vltnBldYn") or "").strip()
        is_violation = vltn_yn in ("Y", "1", "위반")

        main_purpose = (item.findtext("mainPurpsCdNm") or "").strip()
        other_purpose = (item.findtext("etcPurps") or "").strip()

        return BuildingInfo(
            building_name=(item.findtext("bldNm") or "").strip(),
            address=(item.findtext("platPlc") or "").strip(),
            road_address=(item.findtext("newPlatPlc") or "").strip(),
            main_purpose=main_purpose,
            other_purpose=other_purpose,
            structure=(item.findtext("strctCdNm") or "").strip(),
            roof_type=(item.findtext("roofCdNm") or "").strip(),
            total_area=self._safe_float(item.findtext("totArea")),
            building_area=self._safe_float(item.findtext("archArea")),
            ground_floors=ground_floors,
            underground_floors=underground_floors,
            households=self._safe_int(item.findtext("hhldCnt")),
            units=self._safe_int(item.findtext("hoCnt")),
            elevator_count=rider_elv + emgen_elv,
            approval_date=approval_str,
            construction_year=construction_year,
            building_age=now_year - construction_year if construction_year else 0,
            is_violation=is_violation,
            violation_content=(item.findtext("vltnBldCn") or "").strip() if is_violation else "",
            register_type=(item.findtext("regstrKindCdNm") or "").strip(),
            energy_grade=(item.findtext("engrGrade") or "").strip(),
            found=True,
        )

    @staticmethod
    def _analyze_risks(info: BuildingInfo) -> list[str]:
        risks: list[str] = []

        if info.is_violation:
            content = f" ({info.violation_content})" if info.violation_content else ""
            risks.append(
                f"위반건축물{content} — 전세보증보험(HUG) 가입이 불가능하며, "
                "건축법 위반으로 사용 제한·철거 명령 등의 위험이 있습니다"
            )

        purpose_lower = info.main_purpose
        residential_keywords = ("주택", "아파트", "다세대", "다가구", "연립", "공동주택", "오피스텔")
        if purpose_lower and not any(k in purpose_lower for k in residential_keywords):
            risks.append(
                f"건축물 용도: {info.main_purpose} — 주거용이 아닌 건물입니다. "
                "주택임대차보호법이 적용되지 않을 수 있어 전세보증금 보호가 제한됩니다"
            )

        if info.building_age >= 30:
            risks.append(
                f"건축 {info.building_age}년 경과 (사용승인: {info.approval_date[:4]}년) — "
                "노후 건물은 경매 시 낙찰가율이 낮아 보증금 회수 위험이 높아집니다"
            )
        elif info.building_age >= 20:
            risks.append(
                f"건축 {info.building_age}년 경과 — 노후도에 따른 관리 상태 확인을 권장합니다"
            )

        if info.ground_floors and info.ground_floors <= 2 and info.households and info.households >= 4:
            risks.append(
                f"2층 이하 건물에 {info.households}세대 거주 — "
                "불법 분할·쪼개기 전세의 가능성이 있으므로 건축물대장과 실제 구조를 대조하세요"
            )

        return risks

    @staticmethod
    def _safe_int(text: str | None) -> int:
        if not text:
            return 0
        try:
            return int(float(text.strip()))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_float(text: str | None) -> float:
        if not text:
            return 0
        try:
            return float(text.strip())
        except (ValueError, TypeError):
            return 0
