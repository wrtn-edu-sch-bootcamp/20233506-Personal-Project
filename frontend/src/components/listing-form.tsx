"use client";

import { useState, useCallback, useEffect } from "react";
import Script from "next/script";
import type { ListingType, PropertyType, ListingAnalysisRequest, RegistryInput } from "@/lib/types";
import { scrapeListing, analyzeRegistryFile } from "@/lib/api";

export interface ListingFormPrefill {
  address?: string;
  building_name?: string;
  deposit?: number;
  monthly_rent?: number | null;
  area_sqm?: number;
  listing_type?: string;
  property_type?: string;
  listing_text?: string;
  floor?: string;
}

interface ListingFormProps {
  onSubmit: (data: ListingAnalysisRequest) => void;
  isLoading: boolean;
  prefill?: ListingFormPrefill | null;
}

const SQM_PER_PYEONG = 3.3058;

function formatKoreanPrice(manwon: number): string {
  if (!manwon || manwon <= 0) return "";
  const eok = Math.floor(manwon / 10000);
  const remain = manwon % 10000;
  const parts: string[] = [];
  if (eok > 0) parts.push(`${eok.toLocaleString()}억`);
  if (remain > 0) parts.push(`${remain.toLocaleString()}만원`);
  else if (eok > 0) parts.push("원");
  return parts.join(" ");
}

export default function ListingForm({ onSubmit, isLoading, prefill }: ListingFormProps) {
  const [listingType, setListingType] = useState<ListingType>("전세");
  const [propertyType, setPropertyType] = useState<PropertyType>("아파트");
  const [listingText, setListingText] = useState("");

  // Address
  const [address, setAddress] = useState("");
  const [addressDetail, setAddressDetail] = useState("");
  const [buildingName, setBuildingName] = useState("");

  // Price
  const [deposit, setDeposit] = useState("");
  const [monthlyRent, setMonthlyRent] = useState("");

  // Area
  const [areaSqm, setAreaSqm] = useState("");
  const [areaUnit, setAreaUnit] = useState<"sqm" | "pyeong">("sqm");

  // Registry
  const [showRegistry, setShowRegistry] = useState(false);
  const [registryMode, setRegistryMode] = useState<"form" | "text">("form");
  const [regOwner, setRegOwner] = useState("");
  const [regMortgage, setRegMortgage] = useState("");
  const [regSeizure, setRegSeizure] = useState(false);
  const [regTrust, setRegTrust] = useState(false);
  const [regRawText, setRegRawText] = useState("");

  // URL scraping
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [scraping, setScraping] = useState(false);

  useEffect(() => {
    if (!prefill) return;
    if (prefill.address) setAddress(prefill.address);
    if (prefill.building_name) setBuildingName(prefill.building_name);
    if (prefill.deposit) setDeposit(String(prefill.deposit));
    if (prefill.monthly_rent) setMonthlyRent(String(prefill.monthly_rent));
    if (prefill.area_sqm) { setAreaSqm(String(prefill.area_sqm)); setAreaUnit("sqm"); }
    if (prefill.listing_text) setListingText(prefill.listing_text);
    if (prefill.listing_type) {
      const lt = prefill.listing_type as ListingType;
      if (["전세", "월세", "매매"].includes(lt)) setListingType(lt);
    }
    if (prefill.property_type) {
      const pt = prefill.property_type as PropertyType;
      if (["아파트", "연립다세대", "단독다가구", "오피스텔"].includes(pt)) setPropertyType(pt);
    }
  }, [prefill]);

  // Registry file upload
  const [uploadingFile, setUploadingFile] = useState(false);

  const [scrapeMessage, setScrapeMessage] = useState<{ type: "success" | "warning" | "error"; text: string } | null>(null);

  const handleScrapeUrl = async () => {
    if (!scrapeUrl.trim()) return;
    setScraping(true);
    setScrapeMessage(null);
    try {
      const data = await scrapeListing(scrapeUrl.trim());

      const hasData = data.address || data.deposit || data.area_sqm || data.building_name;
      if (!hasData && data.listing_text) {
        setScrapeMessage({ type: "warning", text: data.listing_text });
        return;
      }
      if (!hasData) {
        setScrapeMessage({ type: "error", text: "매물 정보를 추출할 수 없습니다. URL을 확인해주세요." });
        return;
      }

      const filled: string[] = [];
      const missing: string[] = [];

      if (data.address) { setAddress(data.address); filled.push("주소"); }
      else { missing.push("주소"); }
      if (data.building_name) { setBuildingName(data.building_name); filled.push("건물명"); }
      if (data.deposit) { setDeposit(String(data.deposit)); filled.push("보증금/매매가"); }
      else { missing.push("보증금/매매가"); }
      if (data.monthly_rent) { setMonthlyRent(String(data.monthly_rent)); filled.push("월세"); }
      if (data.area_sqm) { setAreaSqm(String(data.area_sqm)); setAreaUnit("sqm"); filled.push("면적"); }
      else { missing.push("면적"); }
      if (data.listing_text) { setListingText(data.listing_text); filled.push("매물설명"); }
      if (data.listing_type) {
        const lt = data.listing_type as ListingType;
        if (["전세", "월세", "매매"].includes(lt)) { setListingType(lt); filled.push("거래유형"); }
      } else { missing.push("거래유형"); }
      if (data.property_type) {
        const pt = data.property_type as PropertyType;
        if (["아파트", "연립다세대", "단독다가구", "오피스텔"].includes(pt)) { setPropertyType(pt); filled.push("건물유형"); }
      }

      let msg = `${data.source}에서 ${filled.length}개 항목(${filled.join(", ")})을 자동 입력했습니다.`;
      if (missing.length > 0) {
        msg += `\n⚠️ ${missing.join(", ")}은(는) 직접 입력해주세요.`;
      }

      setScrapeMessage({
        type: missing.length > 0 ? "warning" : "success",
        text: msg,
      });
    } catch {
      setScrapeMessage({ type: "error", text: "서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요." });
    } finally {
      setScraping(false);
    }
  };

  const handleRegistryFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFile(true);
    try {
      const result = await analyzeRegistryFile(file);
      if (result.owner) setRegOwner(result.owner);
      if (result.mortgage) setRegMortgage(String(result.mortgage));
      setRegSeizure(result.seizure);
      setRegTrust(result.trust);
      if (result.raw_text) setRegRawText(result.raw_text);
      setRegistryMode("form");
    } catch {
      alert("등기부등본 분석에 실패했습니다.");
    } finally {
      setUploadingFile(false);
    }
  };

  const openPostcode = useCallback(() => {
    if (typeof window === "undefined" || !window.daum?.Postcode) return;
    new window.daum.Postcode({
      oncomplete(data: DaumPostcodeData) {
        setAddress(data.roadAddress || data.jibunAddress);
        setBuildingName(data.buildingName || "");
      },
    }).open();
  }, []);

  const finalAreaSqm = areaUnit === "pyeong"
    ? parseFloat(areaSqm) * SQM_PER_PYEONG
    : parseFloat(areaSqm);

  const displayConverted = areaSqm
    ? areaUnit === "sqm"
      ? `≈ ${(parseFloat(areaSqm) / SQM_PER_PYEONG).toFixed(1)}평`
      : `≈ ${(parseFloat(areaSqm) * SQM_PER_PYEONG).toFixed(1)}㎡`
    : "";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const fullAddress = address;

    let registry: RegistryInput | null = null;
    if (showRegistry) {
      if (registryMode === "form" && (regOwner || regMortgage || regSeizure || regTrust)) {
        registry = {
          owner: regOwner || null,
          mortgage: regMortgage ? Number(regMortgage) : null,
          seizure: regSeizure,
          trust: regTrust,
        };
      } else if (registryMode === "text" && regRawText) {
        registry = { seizure: false, trust: false, raw_text: regRawText };
      }
    }

    onSubmit({
      listing_text: listingText,
      listing_type: listingType,
      property_type: propertyType,
      address: fullAddress,
      building_name: buildingName,
      deposit: Number(deposit),
      monthly_rent: listingType === "월세" ? Number(monthlyRent) : null,
      area_sqm: Math.round(finalAreaSqm * 100) / 100,
      registry,
    });
  };

  const LISTING_TYPES: { value: ListingType; label: string }[] = [
    { value: "전세", label: "전세" },
    { value: "월세", label: "월세" },
    { value: "매매", label: "매매" },
  ];

  const PROPERTY_TYPES: { value: PropertyType; label: string; icon: string }[] = [
    { value: "아파트", label: "아파트", icon: "🏢" },
    { value: "연립다세대", label: "연립/다세대", icon: "🏘️" },
    { value: "단독다가구", label: "단독/다가구", icon: "🏠" },
    { value: "오피스텔", label: "오피스텔", icon: "🏬" },
  ];

  const inputCls = "w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none";

  return (
    <>
      <Script src="//t1.daumcdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js" strategy="lazyOnload" />

      {/* URL 스크래핑 로딩 오버레이 */}
      {scraping && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm">
          <div className="mx-4 flex max-w-sm flex-col items-center gap-5 rounded-2xl bg-white p-8 shadow-2xl border border-gray-100">
            <div className="relative flex h-16 w-16 items-center justify-center">
              <div className="absolute inset-0 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
              <span className="text-2xl">🔗</span>
            </div>
            <div className="text-center">
              <h3 className="text-lg font-bold text-gray-900">매물 정보를 불러오는 중</h3>
              <p className="mt-1 text-xs text-gray-500">URL에서 매물 정보를 추출하고 있습니다</p>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
              <div className="h-full animate-loading-bar rounded-full bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-500" />
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* 매물 URL 자동 분석 */}
        <div className="rounded-xl border-2 border-dashed border-blue-200 bg-blue-50/50 p-4">
          <label className="mb-2 flex items-center gap-2 text-sm font-semibold text-blue-700">
            🔗 매물 URL 붙여넣기
            <span className="text-xs font-normal text-blue-500">(직방, 다방, 네이버부동산 등)</span>
          </label>
          <div className="flex gap-2">
            <input
              type="url"
              value={scrapeUrl}
              onChange={e => setScrapeUrl(e.target.value)}
              placeholder="https://www.zigbang.com/home/..."
              className="flex-1 rounded-lg border border-blue-200 bg-white px-4 py-2.5 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
            />
            <button
              type="button"
              onClick={handleScrapeUrl}
              disabled={scraping || !scrapeUrl.trim()}
              className="whitespace-nowrap rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {scraping ? "분석 중..." : "자동 입력"}
            </button>
          </div>
          {!scrapeMessage && (
            <p className="mt-1.5 text-[11px] text-blue-400">URL을 붙여넣으면 매물 정보를 AI가 자동으로 추출하여 아래 폼에 채워줍니다.</p>
          )}
          {scrapeMessage && (
            <div className={`mt-2 rounded-lg px-3 py-2 text-xs ${
              scrapeMessage.type === "success" ? "bg-emerald-50 text-emerald-700" :
              scrapeMessage.type === "warning" ? "bg-yellow-50 text-yellow-700" :
              "bg-red-50 text-red-700"
            }`}>
              <span className="mr-1">{scrapeMessage.type === "success" ? "✅" : scrapeMessage.type === "warning" ? "⚠️" : "❌"}</span>
              <span className="whitespace-pre-line">{scrapeMessage.text}</span>
            </div>
          )}
        </div>

        {/* 매물 유형 */}
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-gray-700">매물 유형</legend>
          <div className="flex gap-2">
            {LISTING_TYPES.map(({ value, label }) => (
              <button key={value} type="button" onClick={() => setListingType(value)}
                className={`flex-1 rounded-lg border-2 px-4 py-2.5 text-sm font-medium transition-all ${listingType === value ? "border-blue-500 bg-blue-50 text-blue-700" : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"}`}>
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        {/* 건물 유형 */}
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-gray-700">건물 유형</legend>
          <div className="grid grid-cols-4 gap-2">
            {PROPERTY_TYPES.map(({ value, label, icon }) => (
              <button key={value} type="button" onClick={() => setPropertyType(value)}
                className={`rounded-lg border-2 px-3 py-2.5 text-sm font-medium transition-all ${propertyType === value ? "border-blue-500 bg-blue-50 text-blue-700" : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"}`}>
                <span className="block text-base">{icon}</span>{label}
              </button>
            ))}
          </div>
        </fieldset>

        {/* 주소 검색 */}
        <div className="space-y-2">
          <label className="mb-1 block text-sm font-semibold text-gray-700">주소</label>
          <div className="flex gap-2">
            <input type="text" readOnly required value={address} placeholder="주소를 검색해주세요"
              className={`${inputCls} cursor-pointer bg-gray-50`} onClick={openPostcode} />
            <button type="button" onClick={openPostcode}
              className="shrink-0 rounded-lg bg-gray-800 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-700">
              주소 검색
            </button>
          </div>
          {address && (
            <div>
              <input type="text" value={addressDetail} onChange={(e) => setAddressDetail(e.target.value)}
                placeholder="상세주소 (선택) — 예: 107동 602호" className={inputCls} />
              <p className="mt-1 text-[11px] text-gray-400">
                상세주소는 참고용이며, 시세 조회에는 도로명 주소만 사용됩니다.
              </p>
            </div>
          )}
          {buildingName && (
            <p className="text-xs text-blue-500">건물/단지명: {buildingName}</p>
          )}
        </div>

        {/* 가격 + 면적 */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="deposit" className="mb-1 flex items-center gap-1 text-sm font-semibold text-gray-700">
              {listingType === "매매" ? "매매가" : "보증금"} (만원)
              {listingType === "전세" && <Tip text="전세 계약 시 임대인에게 맡기는 보증금입니다. 계약 종료 시 전액 돌려받아야 하며, 이 금액이 매매가에 비해 지나치게 높으면 위험합니다." />}
            </label>
            <div className="relative">
              <input id="deposit" type="number" required value={deposit}
                onChange={(e) => setDeposit(e.target.value)} placeholder="예: 30000" className={inputCls} />
              {deposit && Number(deposit) > 0 && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-600">
                  {formatKoreanPrice(Number(deposit))}
                </span>
              )}
            </div>
          </div>
          {listingType === "월세" && (
            <div>
              <label htmlFor="monthlyRent" className="mb-1 block text-sm font-semibold text-gray-700">월세 (만원)</label>
              <div className="relative">
                <input id="monthlyRent" type="number" required value={monthlyRent}
                  onChange={(e) => setMonthlyRent(e.target.value)} placeholder="예: 50" className={inputCls} />
                {monthlyRent && Number(monthlyRent) > 0 && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-600">
                    {formatKoreanPrice(Number(monthlyRent))}
                  </span>
                )}
              </div>
            </div>
          )}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label htmlFor="area" className="text-sm font-semibold text-gray-700">
                면적 ({areaUnit === "sqm" ? "㎡" : "평"})
              </label>
              <button type="button" onClick={() => {
                if (areaSqm) {
                  const val = parseFloat(areaSqm);
                  setAreaSqm(areaUnit === "sqm"
                    ? (val / SQM_PER_PYEONG).toFixed(1)
                    : (val * SQM_PER_PYEONG).toFixed(1));
                }
                setAreaUnit(areaUnit === "sqm" ? "pyeong" : "sqm");
              }}
                className="rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 hover:bg-gray-200">
                {areaUnit === "sqm" ? "평으로 전환" : "㎡로 전환"}
              </button>
            </div>
            <div className="relative">
              <input id="area" type="number" required step="0.1" value={areaSqm}
                onChange={(e) => setAreaSqm(e.target.value)}
                placeholder={areaUnit === "sqm" ? "예: 84.5" : "예: 25.5"} className={inputCls} />
              {displayConverted && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">{displayConverted}</span>
              )}
            </div>
          </div>
        </div>

        {/* 매물 설명 */}
        <div>
          <label htmlFor="listingText" className="mb-1 block text-sm font-semibold text-gray-700">매물 설명</label>
          <textarea id="listingText" required rows={5} value={listingText}
            onChange={(e) => setListingText(e.target.value)}
            placeholder="매물 설명 텍스트를 붙여넣거나 직접 입력해주세요..."
            className={`${inputCls} resize-none leading-relaxed`} />
        </div>

        {/* 등기부등본 (전세) */}
        {listingType === "전세" && (
          <div className="space-y-3">
            <button type="button" onClick={() => setShowRegistry(!showRegistry)}
              className="flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700">
              <svg className={`h-4 w-4 transition-transform ${showRegistry ? "rotate-90" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              등기부등본 정보 입력 (선택)
            </button>

            {showRegistry && (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-4">
                {/* 파일 업로드 */}
                <div className="flex items-center gap-3 rounded-lg border border-dashed border-gray-300 bg-white p-3">
                  <label className="flex cursor-pointer items-center gap-2 rounded-lg bg-indigo-50 px-3 py-2 text-xs font-medium text-indigo-700 hover:bg-indigo-100">
                    📄 PDF/이미지 업로드
                    <input type="file" accept=".pdf,image/*" className="hidden" onChange={handleRegistryFile} />
                  </label>
                  {uploadingFile && <span className="text-xs text-gray-500">AI 분석 중...</span>}
                  <span className="text-[11px] text-gray-400">등기부등본 PDF 또는 사진을 올리면 AI가 자동 분석합니다</span>
                </div>

                {/* 탭 */}
                <div className="flex gap-1 rounded-lg bg-gray-200 p-0.5">
                  {(["form", "text"] as const).map((m) => (
                    <button key={m} type="button" onClick={() => setRegistryMode(m)}
                      className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${registryMode === m ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
                      {m === "form" ? "직접 입력" : "텍스트 붙여넣기"}
                    </button>
                  ))}
                </div>

                {registryMode === "form" ? (
                  <div className="space-y-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 flex items-center gap-1 text-xs font-medium text-gray-600">
                          소유자명
                          <Tip text="등기부등본 갑구에 기재된 현재 소유자 이름입니다. 임대인과 동일인인지 확인하세요." />
                        </label>
                        <input type="text" value={regOwner} onChange={(e) => setRegOwner(e.target.value)}
                          placeholder="홍길동" className={`${inputCls} bg-white text-xs`} />
                      </div>
                      <div>
                        <label className="mb-1 flex items-center gap-1 text-xs font-medium text-gray-600">
                          근저당 설정액 (만원)
                          <Tip text="은행 대출 시 담보로 설정된 금액입니다. 등기부등본 을구에서 확인 가능하며, 이 금액이 크면 전세보증금을 돌려받지 못할 위험이 높아집니다." />
                        </label>
                        <div className="relative">
                          <input type="number" value={regMortgage} onChange={(e) => setRegMortgage(e.target.value)}
                            placeholder="예: 30000" className={`${inputCls} bg-white text-xs`} />
                          {regMortgage && Number(regMortgage) > 0 && (
                            <span className="absolute right-3 top-1/2 -translate-y-1/2 rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">
                              {formatKoreanPrice(Number(regMortgage))}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-x-5 gap-y-2">
                      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                        <input type="checkbox" checked={regSeizure} onChange={(e) => setRegSeizure(e.target.checked)}
                          className="h-4 w-4 rounded border-gray-300 text-red-600 focus:ring-red-500" />
                        <span>압류/가압류 있음</span>
                        <Tip text="법원에서 채무 불이행으로 재산을 동결한 상태입니다. 이 표시가 있으면 해당 매물은 매우 위험하며, 보증금 회수가 어려울 수 있습니다." />
                      </label>
                      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                        <input type="checkbox" checked={regTrust} onChange={(e) => setRegTrust(e.target.checked)}
                          className="h-4 w-4 rounded border-gray-300 text-orange-600 focus:ring-orange-500" />
                        <span>신탁등기 있음</span>
                        <Tip text="부동산을 신탁회사에 맡겨 관리하는 상태입니다. 신탁원부를 확인해야 하고, 신탁회사 동의 없이 계약하면 보증금 보호를 받지 못할 수 있습니다." />
                      </label>
                    </div>
                  </div>
                ) : (
                  <textarea rows={5} value={regRawText} onChange={(e) => setRegRawText(e.target.value)}
                    placeholder="등기부등본 전체 내용을 붙여넣어주세요. AI가 자동으로 소유자, 근저당, 압류 등을 분석합니다."
                    className={`${inputCls} bg-white resize-none text-xs leading-relaxed`} />
                )}
              </div>
            )}
          </div>
        )}

        {/* 제출 */}
        <button type="submit" disabled={isLoading}
          className="w-full rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 focus:ring-4 focus:ring-blue-500/20 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60">
          {isLoading ? (
            <span className="inline-flex items-center gap-2">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
              AI 분석 중...
            </span>
          ) : (
            "매물 분석하기"
          )}
        </button>
      </form>
    </>
  );
}

function Tip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex cursor-help">
      <svg className="h-3.5 w-3.5 text-gray-400 group-hover:text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4m0-4h.01" strokeLinecap="round" />
      </svg>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-56 -translate-x-1/2 rounded-lg bg-gray-900 px-3 py-2 text-[11px] leading-relaxed font-normal text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
        {text}
        <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
      </span>
    </span>
  );
}
