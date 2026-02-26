import type { RiskGrade } from "@/lib/types";

const GRADE_CONFIG: Record<RiskGrade, { emoji: string; bg: string; text: string; border: string }> = {
  "안전": { emoji: "🟢", bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  "주의": { emoji: "🟡", bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
  "경고": { emoji: "🟠", bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
  "위험": { emoji: "🔴", bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
};

export default function RiskBadge({ grade, size = "md" }: { grade: RiskGrade; size?: "sm" | "md" | "lg" }) {
  const config = GRADE_CONFIG[grade];
  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-3 py-1 text-sm",
    lg: "px-4 py-2 text-base",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-semibold ${config.bg} ${config.text} ${config.border} ${sizeClasses[size]}`}
    >
      {config.emoji} {grade}
    </span>
  );
}
