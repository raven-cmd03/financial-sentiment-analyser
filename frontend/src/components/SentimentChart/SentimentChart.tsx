import { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import { useApi } from "@/hooks/useApi";
import { getSentimentHistory } from "@/api/client";
import { useAppContext } from "@/context/AppContext";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import type { TrendData } from "@/types";

interface SentimentChartProps {
  ticker: string;
}

interface ChartPoint {
  date: string;
  dateLabel: string;
  positive: number;
  negative: number;
  neutral: number;
  sentiment: number;
  articles: number;
}

function toChartData(raw: TrendData[]): ChartPoint[] {
  return raw.map((d) => ({
    date: d.date,
    dateLabel: format(parseISO(d.date), "MMM d"),
    positive: d.positive_ratio,
    negative: d.negative_ratio,
    neutral: d.neutral_ratio,
    sentiment: d.sentiment_score,
    articles: d.article_count,
  }));
}

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const articles = payload.find((p) => p.name === "articles")?.value;

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3 shadow-2xl">
      <p className="mb-2 text-[11px] font-semibold text-[var(--color-text-primary)]">
        {label}
      </p>
      {payload
        .filter((p) => p.name !== "articles")
        .map((entry) => (
          <div
            key={entry.name}
            className="flex items-center justify-between gap-6 py-0.5 text-[11px]"
          >
            <span className="capitalize" style={{ color: entry.color }}>
              {entry.name}
            </span>
            <span className="font-mono text-[var(--color-text-primary)]">
              {(entry.value * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      {articles != null && (
        <p className="mt-2 border-t border-[var(--color-border)] pt-1.5 text-[10px] text-[var(--color-text-muted)]">
          {articles} article{articles !== 1 ? "s" : ""} analyzed
        </p>
      )}
    </div>
  );
}

export default function SentimentChart({ ticker }: SentimentChartProps) {
  const { dateRange } = useAppContext();

  const days = useMemo(() => {
    const ms = dateRange.end.getTime() - dateRange.start.getTime();
    return Math.max(7, Math.round(ms / (1000 * 60 * 60 * 24)));
  }, [dateRange]);

  const { data, loading, error, refetch } = useApi(
    () => getSentimentHistory(ticker, days),
    [ticker, days],
  );

  const chartData = useMemo(() => (data ? toChartData(data) : []), [data]);

  if (loading) return <LoadingSpinner message="Fetching sentiment data…" />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;
  if (chartData.length === 0) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6">
        <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">
          No sentiment data available for {ticker.toUpperCase()} yet.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
          Sentiment — {ticker.toUpperCase()}
        </h3>
        <span className="rounded-full bg-[var(--color-bg-tertiary)] px-2.5 py-0.5 text-[10px] font-medium text-[var(--color-text-muted)]">
          {days}d
        </span>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData}>
          <defs>
            <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--color-border)"
            vertical={false}
          />

          <XAxis
            dataKey="dateLabel"
            tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
            axisLine={false}
            tickLine={false}
          />

          <YAxis
            yAxisId="left"
            domain={[0, 1]}
            tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          />

          <YAxis yAxisId="right" orientation="right" hide />

          <Tooltip content={<ChartTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" iconSize={7} />

          <Area
            yAxisId="left"
            type="monotone"
            dataKey="sentiment"
            fill="url(#sentGrad)"
            stroke="none"
            name="sentiment"
          />
          <Line yAxisId="left" type="monotone" dataKey="positive" stroke="#34d399" strokeWidth={2} dot={false} name="positive" />
          <Line yAxisId="left" type="monotone" dataKey="negative" stroke="#f87171" strokeWidth={2} dot={false} name="negative" />
          <Line yAxisId="left" type="monotone" dataKey="neutral" stroke="#6b7280" strokeWidth={1.5} dot={false} strokeDasharray="4 3" name="neutral" />
          <Line yAxisId="right" type="monotone" dataKey="articles" stroke="transparent" dot={false} name="articles" legendType="none" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
