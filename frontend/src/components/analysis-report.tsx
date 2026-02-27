"use client";

import type { AnalysisReport as Report, Severity, MonthlyTrend, AiReportSection, LocationClaim, NearbyFacility, InputSummary } from "@/lib/types";
import ScoreRing from "./score-ring";
import RiskBadge from "./risk-badge";

const SEVERITY_STYLE: Record<Severity, { bg: string; text: string; label: string }> = {
  HIGH: { bg: "bg-red-50", text: "text-red-700", label: "높음" },
  MEDIUM: { bg: "bg-yellow-50", text: "text-yellow-700", label: "보통" },
  LOW: { bg: "bg-gray-50", text: "text-gray-600", label: "낮음" },
};

const CATEGORY_LABEL: Record<string, string> = {
  EXAGGERATION: "과장 표현",
  MISLEADING: "오해 유발",
  PRICE_BAIT: "미끼 가격",
  OMISSION: "정보 누락",
  NORMAL: "정상",
};

const ASSESSMENT_STYLE: Record<string, { icon: string; color: string; label: string }> = {
  "매우적정": { icon: "✅", color: "text-emerald-600", label: "매우 적정 (±5% 이내)" },
  "적정": { icon: "✅", color: "text-emerald-500", label: "적정 (±10% 이내)" },
  "약간고가": { icon: "📈", color: "text-yellow-600", label: "약간 고가 (확인 권장)" },
  "약간저가": { icon: "📉", color: "text-yellow-600", label: "약간 저가 (확인 권장)" },
  "고가의심": { icon: "⚠️", color: "text-orange-600", label: "고가 의심 (주의 필요)" },
  "저가의심": { icon: "⚠️", color: "text-orange-600", label: "저가 의심 (주의 필요)" },
  "과대의심": { icon: "🚨", color: "text-red-600", label: "과대 의심 (사기 가능성)" },
  "과소의심": { icon: "🚨", color: "text-red-600", label: "과소 의심 (사기 가능성)" },
};

function fmtPrice(manwon: number): string {
  const eok = Math.floor(manwon / 10000);
  const remain = manwon % 10000;
  if (eok > 0 && remain > 0) return `${eok}억 ${remain.toLocaleString()}만원`;
  if (eok > 0) return `${eok}억원`;
  return `${manwon.toLocaleString()}만원`;
}

function shortDong(dong: string): string {
  if (!dong) return "-";
  const parts = dong.trim().split(/\s+/);
  return parts[parts.length - 1] || dong;
}

const TYPE_LABEL: Record<string, string> = {
  "전세": "전세",
  "월세": "월세",
  "매매": "매매",
};

const SCORE_TIP: Record<string, string> = {
  "전세": "매물 텍스트 분석, 시세 비교, 전세사기 위험 요소를 종합하여 0~100으로 평가한 점수입니다. 점수가 높을수록 안전한 매물입니다.",
  "월세": "매물 텍스트 분석, 시세 비교, 보증금 안전성을 종합하여 0~100으로 평가한 점수입니다. 점수가 높을수록 안전한 매물입니다.",
  "매매": "매물 텍스트 분석과 시세 비교를 종합하여 0~100으로 평가한 점수입니다. 점수가 높을수록 신뢰할 수 있는 매물입니다.",
};

export default function AnalysisReport({ report, areaSqm = 0 }: { report: Report; areaSqm?: number }) {
  const lt = report.listing_type ?? "전세";
  const isJeonse = lt === "전세";
  const isMonthly = lt === "월세";

  return (
    <div className="space-y-6">
      {/* 종합 점수 */}
      <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-8">
          <ScoreRing score={report.reliability_score} grade={report.reliability_grade} />
          <div className="text-center sm:text-left">
            <div className="mb-1 inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
              {TYPE_LABEL[lt] ?? lt} 분석
            </div>
            <h2 className="flex items-center gap-1 text-lg font-bold text-gray-900">
              종합 신뢰도
              <Tip text={SCORE_TIP[lt] ?? SCORE_TIP["전세"]} />
            </h2>
            <div className="mt-1">
              <RiskBadge grade={report.reliability_grade} size="lg" />
            </div>
          </div>
        </div>
      </section>

      {/* 입력 정보 요약 */}
      {report.input_summary && <InputSummarySection summary={report.input_summary} />}

      {/* AI 종합 평가 요약 */}
      <section className="rounded-2xl border border-blue-100 bg-blue-50/50 p-6 shadow-sm">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-gray-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-sm">💬</span>
          AI 종합 평가
        </h2>
        {report.evaluation ? (
          <p className="text-sm leading-relaxed text-gray-700 whitespace-pre-line">{report.evaluation}</p>
        ) : (
          <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-700">
            <p className="font-medium">AI 평가를 생성하지 못했습니다.</p>
            <p className="mt-1 text-xs text-amber-600">API 호출 한도 초과 등의 이유로 AI 분석이 제한될 수 있습니다. 잠시 후 다시 시도해 주세요.</p>
          </div>
        )}
      </section>

      {/* AI 상세 분석 리포트 */}
      {(report.ai_report ?? []).length > 0 && (
        <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h2 className="mb-5 flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-500 text-sm text-white">AI</span>
            AI 상세 분석 리포트
          </h2>
          <div className="space-y-4">
            {(report.ai_report ?? []).map((section, i) => (
              <AiSection key={i} section={section} />
            ))}
          </div>
        </section>
      )}

      {/* 텍스트 분석 결과 */}
      <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-sm">📝</span>
          매물 텍스트 분석
          <Tip text="매물 설명에 포함된 과장, 허위, 미끼 가격, 중요 정보 누락 등을 AI가 자동으로 탐지합니다." />
        </h2>
        {report.text_analysis.analyzed === false ? (
          <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-700">
            <p className="font-medium">AI 텍스트 분석을 수행하지 못했습니다.</p>
            <p className="mt-1 text-xs text-amber-600">API 호출 한도 초과로 분석이 제한되었습니다. 잠시 후 다시 시도해 주세요.</p>
          </div>
        ) : report.text_analysis.suspicious_expressions.length === 0 ? (
          <div className="rounded-lg bg-emerald-50 p-3">
            <p className="text-sm font-medium text-emerald-700">✅ 의심스러운 표현이 발견되지 않았습니다.</p>
            <p className="mt-1 text-xs text-emerald-600">매물 설명이 비교적 사실적으로 작성된 것으로 판단됩니다.</p>
          </div>
        ) : (
          <ul className="space-y-3">
            {report.text_analysis.suspicious_expressions.map((expr, i) => {
              const style = expr.category === "NORMAL"
                ? { bg: "bg-emerald-50", text: "text-emerald-700", label: "정상" }
                : SEVERITY_STYLE[expr.severity];
              return (
                <li key={i} className={`rounded-lg ${style.bg} p-4`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <span className="font-mono text-sm font-semibold">&ldquo;{expr.text}&rdquo;</span>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <span className="rounded bg-gray-200 px-1.5 py-0.5 text-xs font-medium text-gray-700">
                          {CATEGORY_LABEL[expr.category] ?? expr.category}
                        </span>
                        {expr.category !== "NORMAL" && (
                          <span className={`text-xs font-medium ${style.text}`}>심각도: {style.label}</span>
                        )}
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed text-gray-600">{expr.reason}</p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* 추출 정보 */}
      <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 text-sm">🔍</span>
          핵심 정보 추출
        </h2>
        <dl className="grid gap-3 sm:grid-cols-2">
          {report.extracted_info.price && (
            <InfoItem label="가격" value={report.extracted_info.price} />
          )}
          {report.extracted_info.area && (
            <InfoItem label="면적" value={report.extracted_info.area} />
          )}
          {report.extracted_info.floor && (
            <InfoItem label="층수" value={report.extracted_info.floor} />
          )}
          {report.extracted_info.location_claims.length > 0 && (
            <InfoItem label="위치 특성" value={report.extracted_info.location_claims.join(", ")} />
          )}
          {report.extracted_info.facilities.length > 0 && (
            <InfoItem label="시설/옵션" value={report.extracted_info.facilities.join(", ")} />
          )}
        </dl>
      </section>

      {/* 위치 주장 검증 */}
      {report.location_verification && report.location_verification.claims.length > 0 && (
        <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100 text-sm">📍</span>
            위치 주장 검증
            <Tip text="매물 설명에 포함된 '역세권', '학교 근처' 등의 위치 주장을 카카오맵 API로 실제 검증한 결과입니다." />
          </h2>
          <div className="mb-3 flex items-center gap-3 text-sm">
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
              ✅ 확인됨 {report.location_verification.verified_count}건
            </span>
            {report.location_verification.exaggerated_count > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-1 text-xs font-medium text-orange-700">
                ⚠️ 과장됨 {report.location_verification.exaggerated_count}건
              </span>
            )}
          </div>
          <ul className="space-y-2.5">
            {report.location_verification.claims.map((c, i) => (
              <LocationClaimRow key={i} claim={c} />
            ))}
          </ul>
        </section>
      )}

      {/* 주변 편의시설 */}
      {report.nearby_facilities && <NearbyFacilitiesSection data={report.nearby_facilities} />}

      {/* 시세 비교 */}
      <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100 text-sm">💰</span>
          시세 교차 검증
          <Tip text="입력한 매물의 가격을 국토교통부 실거래가 데이터와 비교합니다. KB부동산 시세 기준: ±5% 매우 적정, ±10% 적정, ±15% 확인 권장, ±25% 주의 필요, ±25% 초과 사기 가능성." />
        </h2>
        {report.market_comparison.avg_market_price ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-gray-500">주변 시세</span>
              <span className="text-lg font-bold text-gray-900">
                {fmtPrice(report.market_comparison.avg_market_price)}
              </span>
              {report.market_comparison.data_count > 0 && (
                <span className="text-xs text-gray-400">
                  (최근 1년 실거래 {report.market_comparison.data_count}건 기준)
                </span>
              )}
              {report.market_comparison.data_scope && (
                <span className="inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-600">
                  {report.market_comparison.data_scope}
                </span>
              )}
            </div>
            {report.market_comparison.deviation_rate !== null && (
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1 text-sm text-gray-500">
                  시세 대비
                  <Tip text="입력한 가격이 주변 실거래 평균 대비 얼마나 차이 나는지 비율(%)입니다. +는 시세보다 비쌈, -는 시세보다 저렴함을 의미합니다." />
                </span>
                <span
                  className={`text-lg font-bold ${
                    Math.abs(report.market_comparison.deviation_rate) <= 10
                      ? "text-emerald-600"
                      : "text-orange-600"
                  }`}
                >
                  {report.market_comparison.deviation_rate > 0 ? "+" : ""}
                  {report.market_comparison.deviation_rate}%
                </span>
              </div>
            )}
            {report.market_comparison.assessment && (
              <p className={`text-sm font-medium ${ASSESSMENT_STYLE[report.market_comparison.assessment]?.color ?? ""}`}>
                {ASSESSMENT_STYLE[report.market_comparison.assessment]?.icon}{" "}
                판정: {ASSESSMENT_STYLE[report.market_comparison.assessment]?.label ?? report.market_comparison.assessment}
              </p>
            )}
            {/* 추가 지표: 시세 추이, 전세가율, 출처 */}
            <div className="mt-3 space-y-1.5 rounded-lg bg-gray-50 p-3">
              {report.market_comparison.price_trend && report.market_comparison.price_trend !== "알수없음" && (
                <p className="text-xs text-gray-600">
                  📊 최근 시세 추이: <span className="font-semibold">{report.market_comparison.price_trend}</span>
                  <span className="text-gray-400"> (최근 3개월 vs 12개월 평균 비교)</span>
                </p>
              )}
              {report.market_comparison.jeonse_rate_market != null && (
                <p className="text-xs text-gray-600">
                  🏠 시장 전세가율: <span className="font-semibold">{report.market_comparison.jeonse_rate_market}%</span>
                  {report.market_comparison.jeonse_rate_risk && (
                    <span className={`ml-1 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      report.market_comparison.jeonse_rate_risk === "안전" ? "bg-emerald-50 text-emerald-700"
                        : report.market_comparison.jeonse_rate_risk === "보통" ? "bg-blue-50 text-blue-700"
                        : report.market_comparison.jeonse_rate_risk === "주의" ? "bg-yellow-50 text-yellow-700"
                        : "bg-red-50 text-red-700"
                    }`}>
                      {report.market_comparison.jeonse_rate_risk}
                    </span>
                  )}
                  <span className="text-gray-400"> (국토연구원 기준: 60% 이하 안전, 80% 이상 위험)</span>
                </p>
              )}
              {report.market_comparison.data_source && (
                <p className="text-[10px] text-gray-400 mt-1">
                  📋 {report.market_comparison.data_source}
                </p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-400">시세 데이터를 조회할 수 없습니다.</p>
        )}

        {/* 월별 시세 트렌드 */}
        <TrendChart trends={report.market_comparison.monthly_trends ?? []} />

        {/* 최근 실거래 내역 */}
        {(() => {
          const trades = report.market_comparison.recent_trades ?? [];
          if (trades.length === 0) return null;
          return (
            <div className="mt-5 border-t border-gray-100 pt-4">
              <h3 className="mb-3 flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
                최근 1년 실거래 내역
                <span className="text-xs font-normal text-gray-400">
                  (국토교통부 실거래가 공개시스템)
                </span>
                {report.market_comparison.data_scope && (
                  <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                    {report.market_comparison.data_scope}
                  </span>
                )}
              </h3>
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-gray-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">거래일</th>
                      <th className="px-3 py-2 font-medium">단지/건물명</th>
                      <th className="px-3 py-2 font-medium">동</th>
                      <th className="px-3 py-2 font-medium text-right">면적</th>
                      <th className="px-3 py-2 font-medium text-right">층</th>
                      <th className="px-3 py-2 font-medium text-right">금액</th>
                      <th className="px-3 py-2 font-medium text-center">유형</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {trades.map((t, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="whitespace-nowrap px-3 py-2 text-gray-600">
                          {t.year}.{String(t.month).padStart(2, "0")}.{String(t.day).padStart(2, "0")}
                        </td>
                        <td className="px-3 py-2 font-medium text-gray-900">{t.name || "-"}</td>
                        <td className="px-3 py-2 text-gray-600">{shortDong(t.dong)}</td>
                        <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                          {t.area_sqm}㎡
                          <span className="ml-1 text-[10px] text-gray-400">({(t.area_sqm / 3.3058).toFixed(0)}평)</span>
                        </td>
                        <td className="px-3 py-2 text-right text-gray-600">
                          {t.floor ? `${t.floor}층` : "-"}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-right font-semibold text-gray-900">
                          {fmtPrice(t.price)}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                            t.trade_type === "매매" ? "bg-blue-50 text-blue-600" : "bg-emerald-50 text-emerald-600"
                          }`}>
                            {t.trade_type}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })()}

        {/* 같은 타입 최근 거래 */}
        {(() => {
          const trades = report.market_comparison.recent_trades ?? [];
          if (trades.length === 0 || !areaSqm) return null;
          const TOLERANCE = 5;
          const sameType = trades.filter(
            (t) => Math.abs(t.area_sqm - areaSqm) <= TOLERANCE,
          );
          if (sameType.length === 0) return null;
          const typeLabel = Math.round(areaSqm);
          const pricePerPyeong = sameType.length > 0
            ? Math.round(sameType.reduce((s, t) => s + t.price / (t.area_sqm / 3.3058), 0) / sameType.length)
            : null;
          return (
            <div className="mt-5 border-t border-gray-100 pt-4">
              <h3 className="mb-3 flex flex-wrap items-center gap-2 text-sm font-semibold text-gray-700">
                같은 타입({typeLabel})의 최근 1년간 거래
                <Tip text={`전용면적 ${areaSqm}㎡ 기준 ±${TOLERANCE}㎡ 범위의 동일 타입 거래 내역입니다.`} />
                <span className="text-xs font-normal text-gray-400">
                  ({sameType.length}건)
                </span>
              </h3>
              {pricePerPyeong && (
                <p className="mb-3 text-xs text-gray-500">
                  같은 타입 평균 3.3㎡당 <span className="font-semibold text-gray-700">{fmtPrice(pricePerPyeong)}</span>
                </p>
              )}
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-gray-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">거래일</th>
                      <th className="px-3 py-2 font-medium text-right">금액</th>
                      <th className="px-3 py-2 font-medium text-right">3.3㎡당</th>
                      <th className="px-3 py-2 font-medium text-right">면적</th>
                      <th className="px-3 py-2 font-medium text-right">층</th>
                      <th className="px-3 py-2 font-medium text-center">유형</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sameType.map((t, i) => {
                      const perPyeong = Math.round(t.price / (t.area_sqm / 3.3058));
                      return (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="whitespace-nowrap px-3 py-2 text-gray-600">
                            {t.year}.{String(t.month).padStart(2, "0")}.{String(t.day).padStart(2, "0")}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right font-semibold text-gray-900">
                            {fmtPrice(t.price)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                            {fmtPrice(perPyeong)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-right text-gray-600">
                            {t.area_sqm}㎡
                          </td>
                          <td className="px-3 py-2 text-right text-gray-600">
                            {t.floor ? `${t.floor}층` : "-"}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <span className={`inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                              t.trade_type === "매매" ? "bg-blue-50 text-blue-600" : "bg-emerald-50 text-emerald-600"
                            }`}>
                              {t.trade_type}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })()}
      </section>

      {/* 월세 보증금 안전 안내 */}
      {isMonthly && report.market_comparison.avg_market_price && (
        <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-sm">🛡️</span>
            보증금 안전 안내
          </h2>
          <div className="space-y-2 text-sm text-gray-700">
            <p>월세 보증금을 보호하려면 다음을 반드시 확인하세요:</p>
            <ul className="ml-4 list-disc space-y-1 text-gray-600">
              <li>전입신고 + 확정일자를 계약 당일에 받으세요</li>
              <li>등기부등본에서 근저당·압류 여부를 확인하세요</li>
              <li>보증금이 크다면 (5천만원 이상) 전세보증금반환보증 가입을 고려하세요</li>
              <li>집주인(소유자)과 계약자가 동일인인지 신분증을 대조하세요</li>
            </ul>
          </div>
        </section>
      )}

      {/* 전세사기 위험 분석 */}
      {report.jeonse_risk && (
        <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-100 text-sm">🛡️</span>
            전세사기 위험 분석
          </h2>
          <div className="mb-4 flex flex-wrap items-center gap-4">
            <RiskBadge grade={report.jeonse_risk.risk_grade} size="lg" />
            <span className="flex items-center gap-1 text-sm text-gray-500">
              위험 점수: <strong>{report.jeonse_risk.risk_score}</strong>/100
              <Tip text="전세가율, 총 부담률, 경매안전율, 권리관계(압류/신탁), 매물 텍스트 등을 종합 분석한 점수입니다. 40 이하 안전, 41~60 경고, 61 이상 위험." />
            </span>
          </div>

          {/* 핵심 지표 카드 */}
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            {report.jeonse_risk.jeonse_rate !== null && (
              <MetricCard
                label="전세가율"
                value={`${report.jeonse_risk.jeonse_rate}%`}
                color={
                  report.jeonse_risk.jeonse_rate >= 90 ? "red"
                  : report.jeonse_risk.jeonse_rate >= 80 ? "orange"
                  : report.jeonse_risk.jeonse_rate >= 70 ? "yellow"
                  : "green"
                }
                tip="매매가 대비 전세가 비율. HUG 기준: 70% 초과 시 보증료 할증. 한국부동산원: 90% 이상 고위험."
              />
            )}
            {report.jeonse_risk.total_burden_ratio !== null && (
              <MetricCard
                label="총 부담률"
                value={`${report.jeonse_risk.total_burden_ratio}%`}
                color={
                  report.jeonse_risk.total_burden_ratio >= 100 ? "red"
                  : report.jeonse_risk.total_burden_ratio >= 90 ? "orange"
                  : report.jeonse_risk.total_burden_ratio >= 80 ? "yellow"
                  : "green"
                }
                tip="(추정실채무액 + 보증금) / 매매가. 채권최고액은 실대출금의 약 120%이므로 ×0.83 보정 적용. 100% 초과 = 깡통전세. 금융위 안전기준: LTV 85% 이내."
              />
            )}
            {report.jeonse_risk.auction_recovery_risk !== null && (
              <MetricCard
                label="경매안전율"
                value={`${report.jeonse_risk.auction_recovery_risk}%`}
                color={
                  report.jeonse_risk.auction_recovery_risk >= 100 ? "red"
                  : report.jeonse_risk.auction_recovery_risk >= 90 ? "orange"
                  : "green"
                }
                tip="(추정실채무+보증금) / (매매가×예상낙찰가율). 100% 초과 시 경매에서도 보증금 전액 회수 불가. 낙찰가율은 물건 유형·지역별 법원경매 통계 기반."
              />
            )}
          </div>

          {report.jeonse_risk.estimated_actual_debt != null && report.jeonse_risk.estimated_actual_debt > 0 && (
            <div className="mb-4 rounded-lg bg-gray-50 px-4 py-3">
              <p className="text-xs text-gray-500">
                근저당 채권최고액에서 추정한 실제 채무액: <strong className="text-gray-700">{fmtPrice(report.jeonse_risk.estimated_actual_debt)}</strong>
                <span className="ml-1 text-gray-400">(채권최고액 × 0.83 보정)</span>
                <Tip text="근저당 설정 시 채권최고액은 실대출금의 약 120%로 설정하는 것이 관행입니다. 따라서 실제 채무는 채권최고액 ÷ 1.2 ≈ 채권최고액 × 0.83으로 추정합니다." />
              </p>
            </div>
          )}

          {report.jeonse_risk.risk_factors.length > 0 && (
            <div className="mb-4">
              <h3 className="mb-2 text-sm font-semibold text-gray-700">위험 요소</h3>
              <ul className="space-y-1.5">
                {report.jeonse_risk.risk_factors.map((factor, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                    <span className="mt-0.5 flex-shrink-0">⚠️</span>
                    <span>{factor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {report.jeonse_risk.risk_factors.length === 0 && (
            <div className="mb-4 rounded-lg bg-emerald-50 p-3">
              <p className="text-sm font-medium text-emerald-700">✅ 주요 위험 요소가 발견되지 않았습니다.</p>
            </div>
          )}

          {/* 전세보증보험 가입 진단 */}
          {report.jeonse_risk.insurance_check && (
            <div className="mb-4 rounded-lg border border-gray-200 p-4">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-700">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-teal-100 text-xs">🛡️</span>
                전세보증보험 가입 가능성
                <Tip text="HUG(주택도시보증공사) 전세보증금반환보증 가입 조건을 기준으로 사전 진단한 결과입니다. 실제 가입 여부는 정식 심사를 통해 결정됩니다." />
              </h3>
              <div className={`mb-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                report.jeonse_risk.insurance_check.eligible
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-orange-50 text-orange-700"
              }`}>
                <span>{report.jeonse_risk.insurance_check.eligible ? "✅" : "⚠️"}</span>
                {report.jeonse_risk.insurance_check.verdict}
              </div>
              {report.jeonse_risk.insurance_check.reasons.length > 0 && (
                <ul className="mb-2 space-y-1">
                  {report.jeonse_risk.insurance_check.reasons.map((r, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
                      <span className="mt-0.5 text-gray-400">•</span>{r}
                    </li>
                  ))}
                </ul>
              )}
              {report.jeonse_risk.insurance_check.tips.length > 0 && (
                <div className="rounded-md bg-blue-50 px-3 py-2">
                  {report.jeonse_risk.insurance_check.tips.map((t, i) => (
                    <p key={i} className="text-[11px] text-blue-700">💡 {t}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {report.jeonse_risk.checklist.length > 0 && (
            <div className="mb-4">
              <h3 className="mb-2 text-sm font-semibold text-gray-700">안전거래 체크리스트</h3>
              <ul className="space-y-1.5">
                {report.jeonse_risk.checklist.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                    <span className="mt-0.5">☐</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rounded-lg border border-gray-100 bg-gray-50/50 px-4 py-3">
            <p className="mb-1 text-[11px] font-semibold text-gray-500">분석 기준 출처</p>
            <ul className="space-y-0.5 text-[10px] text-gray-400">
              <li>• HUG 주택도시보증공사, 전세보증금반환보증 인수기준 (2025 개정)</li>
              <li>• 금융위원회, 주택담보대출 담보인정비율(LTV) 산정기준</li>
              <li>• 한국주택금융공사(HF), 전세 레버리지 리스크 추정 (2023)</li>
              <li>• 국토연구원(KRIHS), 전세사기 방지를 위한 제도개선 방안 (2023)</li>
              <li>• 법원경매 낙찰가율 통계 (2024~2025, 지지옥션/대법원)</li>
            </ul>
          </div>
        </section>
      )}
    </div>
  );
}

function InputSummarySection({ summary }: { summary: InputSummary }) {
  const typeLabel = summary.listing_type || "-";
  const priceLabel = summary.deposit ? fmtPrice(summary.deposit) : "-";
  return (
    <section className="rounded-2xl border border-gray-100 bg-gray-50/50 p-5 shadow-sm">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-bold text-gray-700">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gray-200 text-xs">📋</span>
        분석 매물 정보
      </h2>
      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        {summary.address && (
          <div className="col-span-2 rounded-lg bg-white px-3 py-2">
            <span className="text-gray-400">주소</span>
            <p className="font-medium text-gray-800">{summary.address}</p>
          </div>
        )}
        {summary.building_name && (
          <div className="rounded-lg bg-white px-3 py-2">
            <span className="text-gray-400">건물명</span>
            <p className="font-medium text-gray-800">{summary.building_name}</p>
          </div>
        )}
        <div className="rounded-lg bg-white px-3 py-2">
          <span className="text-gray-400">거래유형</span>
          <p className="font-medium text-gray-800">{typeLabel} · {summary.property_type || "-"}</p>
        </div>
        <div className="rounded-lg bg-white px-3 py-2">
          <span className="text-gray-400">{typeLabel === "매매" ? "매매가" : "보증금"}</span>
          <p className="font-medium text-gray-800">{priceLabel}</p>
        </div>
        {summary.monthly_rent != null && summary.monthly_rent > 0 && (
          <div className="rounded-lg bg-white px-3 py-2">
            <span className="text-gray-400">월세</span>
            <p className="font-medium text-gray-800">{fmtPrice(summary.monthly_rent)}</p>
          </div>
        )}
        {summary.area_sqm > 0 && (
          <div className="rounded-lg bg-white px-3 py-2">
            <span className="text-gray-400">면적</span>
            <p className="font-medium text-gray-800">{summary.area_sqm}㎡ ({summary.area_pyeong}평)</p>
          </div>
        )}
      </div>
    </section>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-gray-50 px-4 py-3">
      <dt className="text-xs font-medium text-gray-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-gray-900">{value}</dd>
    </div>
  );
}

const VERDICT_COLORS: Record<string, string> = {
  "안전": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "적정": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "주의": "bg-yellow-50 text-yellow-700 border-yellow-200",
  "경고": "bg-orange-50 text-orange-700 border-orange-200",
  "위험": "bg-red-50 text-red-700 border-red-200",
};

function getVerdictStyle(verdict: string): string {
  for (const [key, cls] of Object.entries(VERDICT_COLORS)) {
    if (verdict.includes(key)) return cls;
  }
  return "bg-gray-50 text-gray-700 border-gray-200";
}

function AiSection({ section }: { section: AiReportSection }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-4 transition-all hover:shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-bold text-gray-800">
          {section.icon && <span>{section.icon}</span>}
          {section.title}
        </h3>
        {section.verdict && (
          <span className={`whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${getVerdictStyle(section.verdict)}`}>
            {section.verdict}
          </span>
        )}
      </div>
      <p className="text-[13px] leading-relaxed text-gray-600">{section.content}</p>
    </div>
  );
}

function TrendChart({ trends }: { trends: MonthlyTrend[] }) {
  const data = trends.filter(t => t.avg_trade !== null || t.avg_rent !== null);
  if (data.length < 2) return null;

  const allVals = data.flatMap(d => [d.avg_trade, d.avg_rent].filter((v): v is number => v !== null));
  if (allVals.length === 0) return null;
  const minVal = Math.min(...allVals) * 0.9;
  const maxVal = Math.max(...allVals) * 1.05;
  const range = maxVal - minVal || 1;

  const W = 600, H = 180, PAD_L = 55, PAD_R = 15, PAD_T = 15, PAD_B = 30;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  const xStep = data.length > 1 ? plotW / (data.length - 1) : plotW;
  const toY = (v: number) => PAD_T + plotH - ((v - minVal) / range) * plotH;
  const toX = (i: number) => PAD_L + i * xStep;

  const tradeLine = data.map((d, i) => d.avg_trade !== null ? `${i === 0 || data[i-1]?.avg_trade === null ? "M" : "L"}${toX(i)},${toY(d.avg_trade)}` : "").filter(Boolean).join(" ");
  const rentLine = data.map((d, i) => d.avg_rent !== null ? `${i === 0 || data[i-1]?.avg_rent === null ? "M" : "L"}${toX(i)},${toY(d.avg_rent)}` : "").filter(Boolean).join(" ");

  const yTicks = Array.from({length: 4}, (_, i) => minVal + (range * i) / 3);

  return (
    <div className="mt-5 border-t border-gray-100 pt-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-700">
        월별 시세 추이 <span className="text-xs font-normal text-gray-400">(최근 1년)</span>
      </h3>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[600px]" preserveAspectRatio="xMidYMid meet">
          {yTicks.map((v, i) => (
            <g key={i}>
              <line x1={PAD_L} x2={W - PAD_R} y1={toY(v)} y2={toY(v)} stroke="#e5e7eb" strokeDasharray="3,3" />
              <text x={PAD_L - 5} y={toY(v) + 3} textAnchor="end" className="fill-gray-400" fontSize="9">
                {v >= 10000 ? `${(v / 10000).toFixed(1)}억` : `${Math.round(v / 100) * 100}`}
              </text>
            </g>
          ))}
          {data.map((d, i) => i % 2 === 0 ? (
            <text key={i} x={toX(i)} y={H - 5} textAnchor="middle" className="fill-gray-400" fontSize="8">
              {d.month.slice(2)}
            </text>
          ) : null)}
          {tradeLine && <path d={tradeLine} fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />}
          {rentLine && <path d={rentLine} fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />}
          {data.map((d, i) => d.avg_trade !== null ? <circle key={`t${i}`} cx={toX(i)} cy={toY(d.avg_trade)} r="3" fill="#3b82f6" /> : null)}
          {data.map((d, i) => d.avg_rent !== null ? <circle key={`r${i}`} cx={toX(i)} cy={toY(d.avg_rent)} r="3" fill="#10b981" /> : null)}
        </svg>
      </div>
      <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-4 rounded-sm bg-blue-500" /> 매매</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-4 rounded-sm bg-emerald-500" /> 전세</span>
      </div>
    </div>
  );
}

const VERDICT_ICON: Record<string, { icon: string; bg: string; text: string }> = {
  "확인됨": { icon: "✅", bg: "bg-emerald-50", text: "text-emerald-700" },
  "과장됨": { icon: "⚠️", bg: "bg-orange-50", text: "text-orange-700" },
  "확인 불가": { icon: "❓", bg: "bg-gray-50", text: "text-gray-500" },
};

function LocationClaimRow({ claim }: { claim: LocationClaim }) {
  const style = VERDICT_ICON[claim.verdict] ?? VERDICT_ICON["확인 불가"];

  return (
    <li className={`rounded-lg ${style.bg} px-4 py-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm">{style.icon}</span>
            <span className={`text-sm font-semibold ${style.text}`}>{claim.verdict}</span>
            <span className="rounded bg-gray-200/70 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">{claim.category}</span>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            매물 주장: &ldquo;{claim.claim}&rdquo;
            {claim.claimed_walk_min !== null && (
              <span className="ml-1 font-medium">(도보 {claim.claimed_walk_min}분 주장)</span>
            )}
          </p>
          {claim.nearest_name && (
            <p className="mt-1 text-xs text-gray-700">
              가장 가까운 시설: <span className="font-semibold">{claim.nearest_name}</span>
              <span className="ml-1.5 text-gray-500">
                ({claim.actual_distance_m.toLocaleString()}m, 도보 약 {claim.actual_walk_min}분)
              </span>
            </p>
          )}
          {claim.verdict === "과장됨" && claim.claimed_walk_min !== null && (
            <p className="mt-1 text-[11px] text-orange-600">
              주장 도보 {claim.claimed_walk_min}분 → 실제 약 {claim.actual_walk_min}분 (약 {Math.round((claim.actual_walk_min / claim.claimed_walk_min - 1) * 100)}% 더 멀음)
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

const FACILITY_CATEGORIES: {
  key: keyof import("@/lib/types").NearbyFacilities;
  label: string;
  icon: string;
  color: string;
}[] = [
  { key: "subway", label: "지하철역", icon: "🚇", color: "bg-blue-50 text-blue-700" },
  { key: "school", label: "학교", icon: "🏫", color: "bg-amber-50 text-amber-700" },
  { key: "mart", label: "대형마트", icon: "🛒", color: "bg-green-50 text-green-700" },
  { key: "hospital", label: "병원", icon: "🏥", color: "bg-red-50 text-red-700" },
  { key: "park", label: "공원", icon: "🌳", color: "bg-emerald-50 text-emerald-700" },
  { key: "convenience", label: "편의점", icon: "🏪", color: "bg-orange-50 text-orange-700" },
  { key: "cafe", label: "카페", icon: "☕", color: "bg-yellow-50 text-yellow-800" },
  { key: "bank", label: "은행", icon: "🏦", color: "bg-indigo-50 text-indigo-700" },
];

function NearbyFacilitiesSection({ data }: { data: import("@/lib/types").NearbyFacilities }) {
  const hasAny = FACILITY_CATEGORIES.some((c) => (data[c.key] ?? []).length > 0);
  if (!hasAny) return null;

  return (
    <section className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-gray-900">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100 text-sm">🏘️</span>
        주변 편의시설
        <Tip text="매물 주소를 기준으로 반경 500m~1.5km 내 주요 편의시설을 카카오맵으로 검색한 결과입니다." />
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {FACILITY_CATEGORIES.map((cat) => {
          const items: NearbyFacility[] = data[cat.key] ?? [];
          if (items.length === 0) return null;
          return (
            <div
              key={cat.key}
              className="rounded-xl border border-gray-100 bg-gray-50/50 p-3.5 transition-all hover:shadow-sm"
            >
              <div className="mb-2 flex items-center gap-2">
                <span className={`inline-flex h-7 w-7 items-center justify-center rounded-lg text-sm ${cat.color.split(" ")[0]}`}>
                  {cat.icon}
                </span>
                <span className="text-sm font-semibold text-gray-800">{cat.label}</span>
                <span className="ml-auto text-[10px] text-gray-400">{items.length}곳</span>
              </div>
              <ul className="space-y-1.5">
                {items.map((f, i) => (
                  <li key={i} className="flex items-center justify-between text-xs">
                    <span className="truncate text-gray-700" title={f.name}>
                      {f.name}
                    </span>
                    <span className="ml-2 flex-shrink-0 text-gray-400">
                      {f.distance_m >= 1000
                        ? `${(f.distance_m / 1000).toFixed(1)}km`
                        : `${f.distance_m}m`}
                      <span className="ml-1 text-gray-300">|</span>
                      <span className="ml-1">도보 {f.walk_min}분</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}

const METRIC_COLORS: Record<string, { bg: string; text: string; ring: string }> = {
  red: { bg: "bg-red-50", text: "text-red-700", ring: "ring-red-200" },
  orange: { bg: "bg-orange-50", text: "text-orange-700", ring: "ring-orange-200" },
  yellow: { bg: "bg-yellow-50", text: "text-yellow-700", ring: "ring-yellow-200" },
  green: { bg: "bg-emerald-50", text: "text-emerald-700", ring: "ring-emerald-200" },
};

function MetricCard({
  label,
  value,
  color,
  tip,
}: {
  label: string;
  value: string;
  color: "red" | "orange" | "yellow" | "green";
  tip: string;
}) {
  const c = METRIC_COLORS[color];
  return (
    <div className={`rounded-xl ${c.bg} ring-1 ${c.ring} px-4 py-3`}>
      <div className="flex items-center gap-1">
        <span className="text-xs font-medium text-gray-500">{label}</span>
        <Tip text={tip} />
      </div>
      <p className={`mt-1 text-xl font-bold ${c.text}`}>{value}</p>
    </div>
  );
}

function Tip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex cursor-help align-middle">
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
