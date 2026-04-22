import { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import { LineChart as LineChartIcon } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { getMarketData } from "@/api/client";
import { useAppContext } from "@/context/AppContext";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import EmptyState from "@/components/common/EmptyState";
import { ChartCard, ChartTooltip, pickXAxisTicks } from "@/lib/charts";
import type { MarketDataPoint } from "@/types";

interface PriceChartProps {
  ticker: string;
}

interface PricePoint {
  date: string;
  dateLabel: string;
  close: number | null;
  volume: number | null;
  change: number | null;
}

function toChartData(raw: MarketDataPoint[]): PricePoint[] {
  const out: PricePoint[] = [];
  let prev: number | null = null;
  for (const r of raw) {
    const close = typeof r.close === "number" ? r.close : null;
    const change =
      close != null && prev != null && prev !== 0
        ? ((close - prev) / prev) * 100
        : null;
    out.push({
      date: r.date,
      dateLabel: format(parseISO(r.date), "MMM d"),
      close,
      volume: typeof r.volume === "number" ? r.volume : null,
      change,
    });
    if (close != null) prev = close;
  }
  return out;
}

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
}

function PriceTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const close = payload.find((p) => p.name === "close")?.value;
  const volume = payload.find((p) => p.name === "volume")?.value;
  const change = payload.find((p) => p.name === "change")?.value;

  const rows: Parameters<typeof ChartTooltip>[0]["rows"] = [];
  if (close != null) {
    rows.push({ label: "Close", value: `$${close.toFixed(2)}` });
  }
  if (change != null) {
    rows.push({
      label: "Change",
      value: `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`,
      accent: change >= 0 ? "positive" : "negative",
    });
  }
  if (volume != null) {
    rows.push({
      label: "Volume",
      value: Intl.NumberFormat("en", { notation: "compact" }).format(volume),
    });
  }
  return <ChartTooltip title={label ?? ""} rows={rows} />;
}

export default function PriceChart({ ticker }: PriceChartProps) {
  const { dateRange } = useAppContext();

  const days = useMemo(() => {
    const ms = dateRange.end.getTime() - dateRange.start.getTime();
    return Math.max(7, Math.round(ms / (1000 * 60 * 60 * 24)));
  }, [dateRange]);

  const { data, loading, error, refetch } = useApi(
    () => getMarketData(ticker, days),
    [ticker, days],
  );

  const chartData = useMemo(
    () => (data ? toChartData(data.rows) : []),
    [data],
  );
  const ticks = useMemo(
    () => pickXAxisTicks(chartData, "dateLabel", 6),
    [chartData],
  );

  if (loading) return <LoadingSpinner message="Fetching market data…" />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;

  if (chartData.length === 0) {
    return (
      <ChartCard title={`Price — ${ticker.toUpperCase()}`} badge="Alpha Vantage">
        <EmptyState
          icon={LineChartIcon}
          title="No market data yet"
          description={`Prices for ${ticker.toUpperCase()} refresh after the daily market-data collection job runs.`}
        />
      </ChartCard>
    );
  }

  const latest = chartData[chartData.length - 1];
  const first = chartData.find((p) => p.close != null);
  const totalChange =
    latest?.close != null && first?.close != null && first.close !== 0
      ? ((latest.close - first.close) / first.close) * 100
      : null;

  return (
    <ChartCard
      title={`Price — ${ticker.toUpperCase()}`}
      subtitle={
        latest?.close != null
          ? `$${latest.close.toFixed(2)}${
              totalChange != null
                ? ` · ${totalChange >= 0 ? "+" : ""}${totalChange.toFixed(2)}% · ${days}d`
                : ""
            }`
          : undefined
      }
      badge="Alpha Vantage"
    >
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
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
            yAxisId="price"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
            domain={["auto", "auto"]}
          />
          <YAxis yAxisId="vol" orientation="right" hide />
          <Tooltip content={<PriceTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" iconSize={7} />
          <Bar
            yAxisId="vol"
            dataKey="volume"
            fill="hsl(var(--muted))"
            opacity={0.55}
            name="volume"
          />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={false}
            name="close"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
