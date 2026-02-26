"use client";

import { useState, useRef } from "react";

interface ZBRegion {
  name: string;
  lat: number;
  lng: number;
  id: string;
  type: string;
}

interface ZBListing {
  item_id: number;
  sales_type: string;
  service_type: string;
  deposit: number;
  rent: number;
  area_m2: number;
  floor: string;
  address: string;
  title: string;
  image_url: string;
  manage_cost: string;
}

function fmtPrice(manwon: number): string {
  if (!manwon) return "-";
  const eok = Math.floor(manwon / 10000);
  const remain = manwon % 10000;
  if (eok > 0 && remain > 0) return `${eok}억 ${remain.toLocaleString()}`;
  if (eok > 0) return `${eok}억`;
  return `${manwon.toLocaleString()}`;
}

const SALES_OPTIONS = ["전세", "월세", "매매"] as const;
const SERVICE_OPTIONS = ["원룸", "오피스텔", "빌라"] as const;

const AVAILABILITY_NOTES: Record<string, string> = {
  "원룸_매매": "원룸은 전세/월세 위주입니다",
  "오피스텔_매매": "오피스텔은 전세/월세 위주입니다",
  "빌라_매매": "",
  "빌라_전세": "",
  "빌라_월세": "",
};

function getNote(service: string, sales: string): string {
  return AVAILABILITY_NOTES[`${service}_${sales}`] ?? "";
}

export default function ZigbangSearch({
  onSelect,
}: {
  onSelect: (item: {
    address: string;
    building_name: string;
    deposit: number;
    monthly_rent: number | null;
    area_sqm: number;
    listing_type: string;
    property_type: string;
    listing_text: string;
    floor: string;
  }) => void;
}) {
  const [keyword, setKeyword] = useState("");
  const [regions, setRegions] = useState<ZBRegion[]>([]);
  const [listings, setListings] = useState<ZBListing[]>([]);
  const [salesType, setSalesType] = useState<string>("전세");
  const [serviceType, setServiceType] = useState<string>("원룸");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<"search" | "list">("search");
  const [selectedRegion, setSelectedRegion] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const note = getNote(serviceType, salesType);

  const searchRegion = async (q: string) => {
    if (q.length < 2) {
      setRegions([]);
      return;
    }
    try {
      const resp = await fetch(`/api/zigbang/search?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      setRegions(Array.isArray(data) ? data : []);
    } catch {
      setRegions([]);
    }
  };

  const handleKeywordChange = (val: string) => {
    setKeyword(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => searchRegion(val), 300);
  };

  const handleRegionSelect = async (region: ZBRegion) => {
    setSelectedRegion(region.name);
    setRegions([]);
    setLoading(true);
    setStep("list");
    try {
      const params = new URLSearchParams({
        lat: String(region.lat),
        lng: String(region.lng),
        sales_type: salesType,
        service_type: serviceType,
      });
      const resp = await fetch(`/api/zigbang/listings?${params}`);
      const data = await resp.json();
      setListings(Array.isArray(data) ? data : []);
    } catch {
      setListings([]);
    } finally {
      setLoading(false);
    }
  };

  const handleItemSelect = async (item: ZBListing) => {
    let description = "";
    try {
      const resp = await fetch(`/api/zigbang/detail/${item.item_id}`);
      const detail = await resp.json();
      description = detail.description || "";
    } catch {
      /* ignore */
    }

    const propertyMap: Record<string, string> = {
      "원룸": "오피스텔",
      "오피스텔": "오피스텔",
      "빌라": "연립다세대",
      "아파트": "아파트",
    };

    onSelect({
      address: item.address,
      building_name: item.title,
      deposit: item.deposit,
      monthly_rent: item.rent > 0 ? item.rent : null,
      area_sqm: item.area_m2,
      listing_type: item.sales_type || salesType,
      property_type: propertyMap[item.service_type] || propertyMap[serviceType] || "오피스텔",
      listing_text: description,
      floor: item.floor,
    });
  };

  return (
    <div className="rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/50 to-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-sm">🏠</span>
        <h3 className="text-base font-bold text-gray-900">직방 매물 검색</h3>
        <span className="ml-auto rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-600">
          비공식 API
        </span>
      </div>

      {step === "search" && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <div className="flex rounded-lg border border-gray-200 bg-white text-xs">
              {SALES_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setSalesType(opt)}
                  className={`px-3 py-1.5 transition-colors first:rounded-l-lg last:rounded-r-lg ${
                    salesType === opt
                      ? "bg-indigo-600 text-white"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg border border-gray-200 bg-white text-xs">
              {SERVICE_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  onClick={() => setServiceType(opt)}
                  className={`px-3 py-1.5 transition-colors first:rounded-l-lg last:rounded-r-lg ${
                    serviceType === opt
                      ? "bg-indigo-600 text-white"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          {note && (
            <p className="rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-700">
              {note}
            </p>
          )}

          <div className="relative">
            <input
              type="text"
              value={keyword}
              onChange={(e) => handleKeywordChange(e.target.value)}
              placeholder="지역명 검색 (예: 강남역, 대치동, 마포구)"
              className="w-full rounded-lg border border-gray-200 bg-white px-4 py-2.5 text-sm outline-none transition-all focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            />
            {regions.length > 0 && (
              <ul className="absolute z-30 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                {regions.map((r, i) => (
                  <li key={i}>
                    <button
                      onClick={() => handleRegionSelect(r)}
                      className="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-indigo-50 transition-colors"
                    >
                      <span className="font-medium">{r.name}</span>
                      {r.type && (
                        <span className="ml-2 text-xs text-gray-400">{r.type}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p className="text-[10px] text-gray-400 leading-relaxed">
            직방 비공식 API를 통한 검색입니다. 원룸·오피스텔·빌라의 전세/월세 매물이 주로 제공됩니다.
            아파트 매물은 매물 분석 탭에서 직접 입력하세요.
          </p>
        </div>
      )}

      {step === "list" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setStep("search"); setListings([]); }}
              className="flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200 transition-colors"
            >
              ← 다시 검색
            </button>
            <span className="text-sm font-medium text-gray-700">{selectedRegion}</span>
            <span className="text-xs text-gray-400">
              {salesType} · {serviceType} · {listings.length}건
            </span>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
              <span className="ml-2 text-sm text-gray-500">매물을 불러오는 중...</span>
            </div>
          )}

          {!loading && listings.length === 0 && (
            <div className="rounded-lg bg-gray-50 p-6 text-center text-sm text-gray-500">
              해당 조건의 매물을 찾지 못했습니다.
              <br />
              <span className="text-xs text-gray-400">
                {salesType === "매매" && serviceType !== "빌라"
                  ? "직방에서 매매 매물은 빌라에서 주로 제공됩니다. 거래유형이나 건물유형을 변경해보세요."
                  : "검색 조건(거래유형/건물유형)을 변경하거나, 다른 지역으로 검색해보세요."
                }
              </span>
            </div>
          )}

          {!loading && listings.length > 0 && (
            <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
              {listings.map((item) => (
                <button
                  key={item.item_id}
                  onClick={() => handleItemSelect(item)}
                  className="group flex w-full items-start gap-3 rounded-xl border border-gray-100 bg-white p-3 text-left transition-all hover:border-indigo-200 hover:shadow-sm"
                >
                  {item.image_url && (
                    <img
                      src={item.image_url}
                      alt=""
                      className="h-16 w-16 flex-shrink-0 rounded-lg object-cover bg-gray-100"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className={`inline-block rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                        item.sales_type === "매매"
                          ? "bg-blue-50 text-blue-600"
                          : item.sales_type === "월세"
                          ? "bg-orange-50 text-orange-600"
                          : "bg-emerald-50 text-emerald-600"
                      }`}>
                        {item.sales_type}
                      </span>
                      {item.service_type && (
                        <span className="text-[10px] text-gray-400">{item.service_type}</span>
                      )}
                      <span className="truncate text-sm font-semibold text-gray-900">
                        {item.title || "매물"}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-gray-500">{item.address}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-bold text-indigo-700">
                        {item.sales_type === "월세"
                          ? `${fmtPrice(item.deposit)}/${fmtPrice(item.rent)}`
                          : fmtPrice(item.deposit)
                        }
                        <span className="ml-0.5 font-normal text-gray-400">만원</span>
                      </span>
                      {item.area_m2 > 0 && (
                        <span className="text-gray-400">
                          {item.area_m2}㎡ ({Math.round(item.area_m2 / 3.3058)}평)
                        </span>
                      )}
                      {item.floor && <span className="text-gray-400">{item.floor}층</span>}
                    </div>
                  </div>
                  <span className="mt-2 flex-shrink-0 rounded-lg bg-indigo-50 px-2 py-1 text-[10px] font-medium text-indigo-600 opacity-0 transition-opacity group-hover:opacity-100">
                    분석하기 →
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
