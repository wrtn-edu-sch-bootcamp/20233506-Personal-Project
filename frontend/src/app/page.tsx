"use client";

import { useState, useEffect, useRef } from "react";
import ListingForm from "@/components/listing-form";
import AnalysisReport from "@/components/analysis-report";
import ComparisonView, { getReports, saveReport, removeReport } from "@/components/comparison-view";
import type { ListingAnalysisRequest, AnalysisReport as Report } from "@/lib/types";
import { analyzeListing } from "@/lib/api";

const LOADING_MESSAGES = [
  "매물 텍스트를 분석하고 있습니다...",
  "주변 실거래가를 조회하고 있습니다...",
  "등기부등본 위험 요소를 확인 중입니다...",
  "AI가 종합 리포트를 작성 중입니다...",
  "전세보증보험 가입 가능성을 진단 중입니다...",
  "거의 완료되었습니다. 조금만 기다려주세요...",
];

type Tab = "input" | "result" | "compare";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "input", label: "매물 분석", icon: "📝" },
  { id: "result", label: "분석 결과", icon: "📊" },
  { id: "compare", label: "매물 비교", icon: "⚖️" },
];

export default function HomePage() {
  const [tab, setTab] = useState<Tab>("input");
  const [report, setReport] = useState<Report | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedCount, setSavedCount] = useState(0);
  const [lastAddress, setLastAddress] = useState("");
  const [lastAreaSqm, setLastAreaSqm] = useState(0);
  const [loadingMsg, setLoadingMsg] = useState(LOADING_MESSAGES[0]);
  const loadingInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const [prefillKey, setPrefillKey] = useState(0);

  useEffect(() => {
    setSavedCount(getReports().length);
  }, [tab]);

  useEffect(() => {
    if (isLoading) {
      let idx = 0;
      setLoadingMsg(LOADING_MESSAGES[0]);
      loadingInterval.current = setInterval(() => {
        idx = Math.min(idx + 1, LOADING_MESSAGES.length - 1);
        setLoadingMsg(LOADING_MESSAGES[idx]);
      }, 8000);
    } else if (loadingInterval.current) {
      clearInterval(loadingInterval.current);
      loadingInterval.current = null;
    }
    return () => {
      if (loadingInterval.current) clearInterval(loadingInterval.current);
    };
  }, [isLoading]);

  const handleSubmit = async (data: ListingAnalysisRequest) => {
    setIsLoading(true);
    setError(null);
    setReport(null);
    setLastAddress(data.address);
    setLastAreaSqm(data.area_sqm);

    try {
      const result = await analyzeListing(data);
      setReport(result);
      setTab("result");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("429") || msg.includes("rate") || msg.includes("quota")) {
        setError("AI API 요청 한도를 초과했습니다. 잠시 후(약 1분) 다시 시도해주세요.");
      } else if (msg.includes("Failed to fetch") || msg.includes("fetch")) {
        setError("서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.");
      } else {
        setError(msg || "분석 중 오류가 발생했습니다.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = () => {
    if (!report) return;
    const label = lastAddress.split(" ").slice(-2).join(" ") || "매물";
    saveReport(label, lastAddress, report);
    setSavedCount(getReports().length);
    alert("비교함에 저장되었습니다.");
  };

  const handleRemove = (id: string) => {
    removeReport(id);
    setSavedCount(getReports().length);
  };

  return (
    <div className="space-y-6">
      {/* Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm">
          <div className="mx-4 flex max-w-md flex-col items-center gap-6 rounded-3xl bg-white p-10 shadow-2xl border border-gray-100">
            <div className="relative flex h-20 w-20 items-center justify-center">
              <div className="absolute inset-0 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
              <span className="text-3xl">🔍</span>
            </div>
            <div className="text-center">
              <h3 className="text-xl font-bold text-gray-900">AI 분석 중입니다</h3>
              <p className="mt-1 text-sm text-gray-500">조금만 기다려주세요</p>
            </div>
            <p className="min-h-[2.5rem] text-center text-sm font-medium text-blue-600 transition-all duration-500">
              {loadingMsg}
            </p>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
              <div className="h-full animate-loading-bar rounded-full bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-500" />
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="text-center pt-2">
        <h1 className="text-2xl font-extrabold tracking-tight text-gray-900 sm:text-3xl">
          SafeHome
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          AI 기반 부동산 매물 신뢰도 분석 시스템
        </p>
      </header>

      {/* Tab Navigation */}
      <nav className="sticky top-14 z-40 -mx-4 bg-white/95 backdrop-blur-sm border-b border-gray-200 px-4">
        <div className="flex">
          {TABS.map((t) => {
            const isActive = tab === t.id;
            const badge = t.id === "compare" && savedCount > 0 ? savedCount : t.id === "result" && report ? "✓" : null;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`relative flex flex-1 items-center justify-center gap-1.5 px-2 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? "text-blue-600"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                <span className="text-base">{t.icon}</span>
                <span className="hidden sm:inline">{t.label}</span>
                {badge !== null && (
                  <span className="inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-blue-100 px-1 text-[10px] font-bold text-blue-700">
                    {badge}
                  </span>
                )}
                {isActive && (
                  <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-blue-600" />
                )}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Tab: 매물 분석 (입력 폼) */}
      {tab === "input" && (
        <div className="space-y-4">
          <section className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-7">
            <ListingForm key={prefillKey} onSubmit={handleSubmit} isLoading={isLoading} />
          </section>
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <strong>오류:</strong> {error}
            </div>
          )}
        </div>
      )}

      {/* Tab: 분석 결과 */}
      {tab === "result" && (
        <div className="space-y-4">
          {report ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-gray-900">분석 결과</h2>
                <div className="flex gap-2">
                  <button
                    onClick={handleSave}
                    className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
                  >
                    💾 비교함에 저장
                  </button>
                  <button
                    onClick={() => setTab("input")}
                    className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-200 transition-colors"
                  >
                    새 분석
                  </button>
                </div>
              </div>
              <AnalysisReport report={report} areaSqm={lastAreaSqm} />
            </>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-gray-50/50 py-20 text-center">
              <span className="text-4xl">📊</span>
              <p className="mt-4 text-sm font-medium text-gray-500">아직 분석 결과가 없습니다</p>
              <p className="mt-1 text-xs text-gray-400">매물 분석 탭에서 분석을 시작하세요</p>
              <button
                onClick={() => setTab("input")}
                className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
              >
                매물 분석하기
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tab: 매물 비교 */}
      {tab === "compare" && (
        <ComparisonView
          reports={getReports()}
          onClose={() => setTab("input")}
          onRemove={handleRemove}
          onView={(r) => {
            setReport(r);
            setTab("result");
          }}
        />
      )}
    </div>
  );
}
