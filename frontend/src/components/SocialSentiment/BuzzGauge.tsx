interface BuzzGaugeProps {
  score: number;
}

function getColor(score: number): string {
  if (score < 30) return "#6b7280";
  if (score < 60) return "#eab308";
  return score >= 80 ? "#ef4444" : "#22c55e";
}

function getTrackColor(score: number): string {
  if (score < 30) return "rgba(107,114,128,0.2)";
  if (score < 60) return "rgba(234,179,8,0.2)";
  return score >= 80 ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)";
}

export default function BuzzGauge({ score }: BuzzGaugeProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const color = getColor(clamped);
  const trackColor = getTrackColor(clamped);

  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-36 w-36">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 128 128">
          <circle
            cx="64"
            cy="64"
            r={radius}
            fill="none"
            stroke={trackColor}
            strokeWidth="10"
          />
          <circle
            cx="64"
            cy="64"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-white">{clamped}</span>
        </div>
      </div>
      <span className="mt-1 text-xs font-medium text-gray-400">X Buzz</span>
    </div>
  );
}
