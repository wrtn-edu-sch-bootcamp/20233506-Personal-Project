"use client";

import type { AnalysisReport } from "@/lib/types";

interface SavedReport {
  id: string;
  label: string;
  address: string;
  savedAt: string;
  report: AnalysisReport;
}

function fmtPrice(manwon: number): string {
  const eok = Math.floor(manwon / 10000);
  const remain = manwon % 10000;
  if (eok > 0 && remain > 0) return `${eok}억 ${remain.toLocaleString()}만원`;
  if (eok > 0) return `${eok}억원`;
  return `${manwon.toLocaleString()}만원`;
}

const GRADE_STYLE: Record<string, { bg: string; text: string }> = {
  "안전": { bg: "bg-emerald-50", text: "text-emerald-700" },
  "주의": { bg: "bg-yellow-50", text: "text-yellow-700" },
  "경고": { bg: "bg-orange-50", text: "text-orange-700" },
  "위험": { bg: "bg-red-50", text: "text-red-700" },
};

export function getReports(): SavedReport[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem("safehome_reports") || "[]");
  } catch {
    return [];
  }
}

export function saveReport(label: string, address: string, report: AnalysisReport): void {
  const reports = getReports();
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  reports.unshift({ id, label, address, savedAt: new Date().toISOString(), report });
  if (reports.length > 20) reports.length = 20;
  localStorage.setItem("safehome_reports", JSON.stringify(reports));
}

export function removeReport(id: string): void {
  const reports = getReports().filter(r => r.id !== id);
  localStorage.setItem("safehome_reports", JSON.stringify(reports));
}

export default function ComparisonView({
  reports,
  onClose,
  onRemove,
  onView,
}: {
  reports: SavedReport[];
  onClose: () => void;
  onRemove: (id: string) => void;
  onView?: (report: AnalysisReport) => void;
}) {
  if (reports.length === 0) {
    return (
      <div className="rounded-2xl border border-gray-100 bg-white p-8 text-center shadow-sm">
        <p className="text-gray-400">비교할 매물이 없습니다. 분석 결과를 저장한 뒤 비교해보세요.</p>
        <button onClick={onClose} className="mt-4 text-sm text-blue-600 hover:underline">닫기</button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-900">매물 비교</h2>
        <button onClick={onClose} className="text-sm text-gray-400 hover:text-gray-600">닫기 ✕</button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 text-xs text-gray-500">
              <th className="px-3 py-2 text-left font-medium">항목</th>
              {reports.map(r => (
                <th key={r.id} className="min-w-[160px] px-3 py-2 text-left font-medium">
                  <div className="flex flex-col gap-0.5">
                    <span className="truncate max-w-[150px] font-semibold text-gray-700">{r.label || r.address}</span>
                    <span className="text-[10px] font-normal text-gray-400">
                      {new Date(r.savedAt).toLocaleDateString("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            <Row label="주소">
              {reports.map(r => (
                <td key={r.id} className="px-3 py-2 text-xs text-gray-600 truncate max-w-[180px]">{r.address}</td>
              ))}
            </Row>
            <Row label="신뢰도">
              {reports.map(r => {
                const g = GRADE_STYLE[r.report.reliability_grade] ?? { bg: "bg-gray-50", text: "text-gray-700" };
                return (
                  <td key={r.id} className="px-3 py-2">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${g.bg} ${g.text}`}>
                      {r.report.reliability_score}점 · {r.report.reliability_grade}
                    </span>
                  </td>
                );
              })}
            </Row>
            <Row label="시세 평균">
              {reports.map(r => (
                <td key={r.id} className="px-3 py-2 text-xs font-medium text-gray-900">
                  {r.report.market_comparison.avg_market_price
                    ? fmtPrice(r.report.market_comparison.avg_market_price)
                    : "-"}
                </td>
              ))}
            </Row>
            <Row label="시세 편차">
              {reports.map(r => (
                <td key={r.id} className={`px-3 py-2 text-xs font-semibold ${
                  r.report.market_comparison.deviation_rate !== null &&
                  Math.abs(r.report.market_comparison.deviation_rate) > 10
                    ? "text-orange-600" : "text-emerald-600"
                }`}>
                  {r.report.market_comparison.deviation_rate !== null
                    ? `${r.report.market_comparison.deviation_rate > 0 ? "+" : ""}${r.report.market_comparison.deviation_rate}%`
                    : "-"}
                </td>
              ))}
            </Row>
            <Row label="전세가율">
              {reports.map(r => (
                <td key={r.id} className={`px-3 py-2 text-xs font-semibold ${
                  r.report.jeonse_risk?.jeonse_rate && r.report.jeonse_risk.jeonse_rate >= 80
                    ? "text-red-600" : "text-gray-700"
                }`}>
                  {r.report.jeonse_risk?.jeonse_rate !== null && r.report.jeonse_risk?.jeonse_rate !== undefined
                    ? `${r.report.jeonse_risk.jeonse_rate}%`
                    : "-"}
                </td>
              ))}
            </Row>
            <Row label="위험 점수">
              {reports.map(r => (
                <td key={r.id} className="px-3 py-2 text-xs text-gray-700">
                  {r.report.jeonse_risk ? `${r.report.jeonse_risk.risk_score}/100` : "-"}
                </td>
              ))}
            </Row>
            <Row label="보증보험">
              {reports.map(r => {
                const ins = r.report.jeonse_risk?.insurance_check;
                if (!ins) return <td key={r.id} className="px-3 py-2 text-xs text-gray-400">-</td>;
                return (
                  <td key={r.id} className={`px-3 py-2 text-xs font-medium ${ins.eligible ? "text-emerald-600" : "text-orange-600"}`}>
                    {ins.eligible ? "✅ 가능" : "⚠️ 제한"}
                  </td>
                );
              })}
            </Row>
            <Row label="의심 표현">
              {reports.map(r => (
                <td key={r.id} className="px-3 py-2 text-xs text-gray-700">
                  {r.report.text_analysis.suspicious_expressions.length}건
                </td>
              ))}
            </Row>
            <tr className="border-t border-gray-200 bg-gray-50/50">
              <td className="px-3 py-3 text-xs font-medium text-gray-500">관리</td>
              {reports.map(r => (
                <td key={r.id} className="px-3 py-3">
                  <div className="flex items-center gap-2">
                    {onView && (
                      <button
                        onClick={() => onView(r.report)}
                        className="rounded-md bg-blue-50 px-2.5 py-1.5 text-[11px] font-medium text-blue-600 hover:bg-blue-100 transition-colors"
                      >
                        📄 다시보기
                      </button>
                    )}
                    <button
                      onClick={() => {
                        if (confirm(`"${r.label || r.address}" 매물을 비교함에서 삭제하시겠습니까?`)) {
                          onRemove(r.id);
                        }
                      }}
                      className="rounded-md bg-red-50 px-2.5 py-1.5 text-[11px] font-medium text-red-600 hover:bg-red-100 transition-colors"
                    >
                      🗑 삭제
                    </button>
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr className="hover:bg-gray-50/50">
      <td className="whitespace-nowrap px-3 py-2 text-xs font-medium text-gray-500">{label}</td>
      {children}
    </tr>
  );
}
