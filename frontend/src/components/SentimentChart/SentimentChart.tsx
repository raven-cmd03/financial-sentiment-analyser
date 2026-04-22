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
import EmptyState from "@/components/common/EmptyState";
import { ChartCard, ChartTooltip, pickXAxisTicks } from "@/lib/charts";
import { LineChart as LineChartIcon } from "lucide-react";
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
  score: number;
  articles: number;
}

function toChartData(raw: TrendData[]): ChartPoint[] {
  return raw.map((d) => ({
    date: d.date,
    dateLabel: format(parseISO(d.date), "MMM d"),
    positive: d.positive_ratio,
    negative: d.negative_ratio,
    neutral: d.neutral_ratio,
    score: d.sentiment_score,
    articles: d.article_count,
  }));
}

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
}

function SentimentTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const articles = payload.find((p) => p.name === "articles")?.value;

  const rows = payload
    .filter((p) => p.name !== "articles" && p.name !== "score")
    .map((p) => ({
      label: p.name,
      value: `${(p.value * 100).toFixed(1)}%`,
      color: p.color,
    }));

  const score = payload.find((p) => p.name === "score")?.value;

  if (score !== undefined) {
    rows.unshift({
      label: "Net score",
      value: `${score >= 0 ? "+" : ""}${(score * 100).toFixed(1)}`,
      color: "hsl(var(--primary))",
    });
  }

  return (
    <ChartTooltip
      title={`${label ?? ""}${
        articles != null ? ` · ${articles} article${articles !== 1 ? "s" : ""}` : ""
      }`}
      rows={rows}
    />
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
  const ticks = useMemo(
    () => pickXAxisTicks(chartData, "dateLabel", 6),
    [chartData],
  );

  if (loading) return <LoadingSpinner message="Fetching sentiment data…" />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;

  if (chartData.length === 0) {
    return (
      <ChartCard
        title={`Sentiment — ${ticker.toUpperCase()}`}
        badge={`${days}d`}
      >
        <EmptyState
          icon={LineChartIcon}
          title="No sentiment data yet"
          description={`We haven't scored any articles for ${ticker.toUpperCase()} in this range. Try widening the window.`}
        />
      </ChartCard>
    );
  }

  return (
    <ChartCard
      title={`Sentiment — ${ticker.toUpperCase()}`}
      subtitle="Probability mix per day"
      badge={`${days}d`}
    >
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <defs>
            <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="hsl(var(--border))"
            vertical={false}
          />
          <XAxis
            dataKey="dateLabel"
            ticks={ticks}
            interval="preserveStartEnd"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="left"
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          />
          <YAxis yAxisId="right" orientation="right" hide />
          <Tooltip content={<SentimentTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" iconSize={7} />

          <Area
            yAxisId="left"
            type="monotone"
            dataKey="score"
            fill="url(#sentGrad)"
            stroke="none"
            name="score"
            legendType="none"
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="positive"
            stroke="hsl(var(--positive))"
            strokeWidth={2}
            dot={false}
            name="positive"
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="negative"
            stroke="hsl(var(--negative))"
            strokeWidth={2}
            dot={false}
            name="negative"
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="neutral"
            stroke="hsl(var(--muted-foreground))"
            strokeWidth={1.5}
            dot={false}
            strokeDasharray="4 3"
            name="neutral"
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="articles"
            stroke="transparent"
            dot={false}
            name="articles"
            legendType="none"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
