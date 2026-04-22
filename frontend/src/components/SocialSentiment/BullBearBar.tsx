interface BullBearBarProps {
  bullish: number;
  bearish: number;
}

export default function BullBearBar({ bullish, bearish }: BullBearBarProps) {
  const bullPct = Math.round(bullish * 100);
  const bearPct = Math.round(bearish * 100);

  return (
    <div className="w-full">
      <div className="mb-1.5 flex items-center justify-between text-xs font-medium">
        <span className="text-emerald-400">Bullish {bullPct}%</span>
        <span className="text-red-400">Bearish {bearPct}%</span>
      </div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-gray-700">
        <div
          className="bg-emerald-500 transition-all duration-500 ease-out"
          style={{ width: `${bullPct}%` }}
        />
        <div
          className="bg-red-500 transition-all duration-500 ease-out"
          style={{ width: `${bearPct}%` }}
        />
      </div>
    </div>
  );
}
