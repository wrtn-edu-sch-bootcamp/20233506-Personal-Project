"use client";

import type { RiskGrade } from "@/lib/types";

const GRADE_COLOR: Record<RiskGrade, string> = {
  "안전": "#10b981",
  "주의": "#eab308",
  "경고": "#f97316",
  "위험": "#ef4444",
};

export default function ScoreRing({ score, grade }: { score: number; grade: RiskGrade }) {
  const color = GRADE_COLOR[grade];
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="140" height="140" className="-rotate-90">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#e5e7eb" strokeWidth="10" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold" style={{ color }}>{score}</span>
        <span className="text-xs text-gray-500">/ 100</span>
      </div>
    </div>
  );
}
