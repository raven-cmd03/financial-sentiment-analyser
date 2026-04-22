import { cn } from "@/lib/utils";

interface SentimentBadgeProps {
  label: "positive" | "negative" | "neutral";
  score?: number;
  confidence?: number;
  className?: string;
}

const toneClasses = {
  positive: "bg-positive/15 text-positive",
  negative: "bg-negative/15 text-negative",
  neutral: "bg-muted text-muted-foreground",
} as const;

export default function SentimentBadge({
  label,
  score,
  confidence,
  className,
}: SentimentBadgeProps) {
  const tone = toneClasses[label] ?? toneClasses.neutral;
  const displayValue = score ?? confidence;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold capitalize",
        tone,
        className,
      )}
    >
      {label}
      {displayValue !== undefined && (
        <span className="opacity-70">
          {(displayValue * 100).toFixed(0)}%
        </span>
      )}
    </span>
  );
}
