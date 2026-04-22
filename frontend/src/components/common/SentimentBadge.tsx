interface SentimentBadgeProps {
  label: "positive" | "negative" | "neutral";
  score?: number;
  confidence?: number;
}

const config = {
  positive: {
    bg: "bg-[var(--color-positive)]/10",
    text: "text-[var(--color-positive)]",
  },
  negative: {
    bg: "bg-[var(--color-negative)]/10",
    text: "text-[var(--color-negative)]",
  },
  neutral: {
    bg: "bg-[var(--color-neutral)]/10",
    text: "text-[var(--color-neutral)]",
  },
} as const;

export default function SentimentBadge({
  label,
  score,
  confidence,
}: SentimentBadgeProps) {
  const c = config[label];
  const displayValue = score ?? confidence;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold capitalize ${c.bg} ${c.text}`}
    >
      {label}
      {displayValue !== undefined && (
        <span className="opacity-60">{(displayValue * 100).toFixed(0)}%</span>
      )}
    </span>
  );
}
