import { useApi } from "@/hooks/useApi";
import { getSocialHistory } from "@/api/client";
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { Loader2 } from "lucide-react";

interface SocialTrendProps {
  ticker: string;
}

export default function SocialTrend({ ticker }: SocialTrendProps) {
  const { data, loading, error } = useApi(
    () => getSocialHistory(ticker, 7),
    [ticker],
  );

  if (loading) {
    return (
      <div className="flex h-16 items-center justify-center">
        <Loader2 className="h-4 w-4 animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  if (error || !data || data.length === 0) {
    return (
      <div className="flex h-16 items-center justify-center text-xs text-[var(--color-text-muted)]">
        No trend data
      </div>
    );
  }

  const chartData = data
    .slice()
    .reverse()
    .map((d) => ({
      date: d.fetched_at ?? "",
      score: Number(d.buzz_score ?? 0),
    }));

  return (
    <div className="h-16 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <YAxis domain={["dataMin - 5", "dataMax + 5"]} hide />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--color-bg-secondary)",
              border: "1px solid var(--color-border)",
              borderRadius: "0.5rem",
              fontSize: "0.75rem",
              color: "var(--color-text-primary)",
            }}
            labelFormatter={() => ""}
            formatter={(value: number) => [value.toFixed(1), "Buzz"]}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="var(--color-accent)"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
