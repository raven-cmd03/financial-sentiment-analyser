import { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { format, parseISO } from "date-fns";
import {
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  ArrowUpDown,
} from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { getTrends, getCompanies, getSentimentHistory } from "@/api/client";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import EmptyState from "@/components/common/EmptyState";
import SentimentBadge from "@/components/common/SentimentBadge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import { ChartCard, ChartTooltip, pickXAxisTicks } from "@/lib/charts";
import { cn } from "@/lib/utils";
import type { Company, TrendData } from "@/types";

interface ChartPoint {
  date: string;
  dateLabel: string;
  score: number;
  positive: number;
  negative: number;
  articles: number;
}

function toChartData(raw: TrendData[]): ChartPoint[] {
  return raw.map((d) => ({
    date: d.date,
    dateLabel: format(parseISO(d.date), "MMM d"),
    score: d.sentiment_score,
    positive: d.positive_ratio,
    negative: d.negative_ratio,
    articles: d.article_count,
  }));
}

interface CompanyRank {
  ticker: string;
  name: string;
  score: number;
  articles: number;
}

function rankCompanies(
  companies: Company[],
  histories: Map<string, TrendData[]>,
): CompanyRank[] {
  const scores: CompanyRank[] = [];
  for (const c of companies) {
    const hist = histories.get(c.ticker);
    if (!hist || hist.length === 0) continue;
    const avg =
      hist.reduce((sum, d) => sum + d.sentiment_score, 0) / hist.length;
    const articles = hist.reduce((sum, d) => sum + d.article_count, 0);
    scores.push({ ticker: c.ticker, name: c.name, score: avg, articles });
  }
  return scores;
}

interface TooltipEntry {
  name: string;
  value: number;
  color: string;
}

function TrendTooltipBody({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const articles = payload.find((p) => p.name === "articles")?.value;
  const score = payload.find((p) => p.name === "score")?.value;

  const rows: Parameters<typeof ChartTooltip>[0]["rows"] = [];
  if (score !== undefined) {
    rows.push({
      label: "Net score",
      value: `${score >= 0 ? "+" : ""}${(score * 100).toFixed(1)}`,
      color: "hsl(var(--primary))",
    });
  }
  for (const p of payload) {
    if (p.name === "articles" || p.name === "score") continue;
    rows.push({
      label: p.name,
      value: `${(p.value * 100).toFixed(1)}%`,
      color: p.color,
    });
  }
  return (
    <ChartTooltip
      title={`${label ?? ""}${
        articles !== undefined
          ? ` · ${articles} article${articles !== 1 ? "s" : ""}`
          : ""
      }`}
      rows={rows}
    />
  );
}

type SortKey = "score" | "articles" | "ticker";
type SortDir = "asc" | "desc";

function RankTable({
  title,
  items,
  variant,
}: {
  title: string;
  items: CompanyRank[];
  variant: "positive" | "negative";
}) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>(
    variant === "positive" ? "desc" : "asc",
  );

  const sorted = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      let diff = 0;
      if (sortKey === "ticker") diff = a.ticker.localeCompare(b.ticker);
      else diff = a[sortKey] - b[sortKey];
      return sortDir === "asc" ? diff : -diff;
    });
    return copy.slice(0, 5);
  }, [items, sortKey, sortDir]);

  const toggle = (k: SortKey) => {
    if (k === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir(k === "score" ? (variant === "positive" ? "desc" : "asc") : "desc");
    }
  };

  const Arrow = variant === "positive" ? ArrowUpRight : ArrowDownRight;

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0 p-4">
        <Arrow
          className={cn(
            "h-4 w-4",
            variant === "positive" ? "text-positive" : "text-negative",
          )}
        />
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {sorted.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-muted-foreground">
            No data available
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">#</TableHead>
                <TableHead>
                  <button
                    className="flex items-center gap-1 uppercase"
                    onClick={() => toggle("ticker")}
                  >
                    Ticker
                    <ArrowUpDown className="h-3 w-3 opacity-50" />
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button
                    className="ml-auto flex items-center gap-1 uppercase"
                    onClick={() => toggle("articles")}
                  >
                    Articles
                    <ArrowUpDown className="h-3 w-3 opacity-50" />
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button
                    className="ml-auto flex items-center gap-1 uppercase"
                    onClick={() => toggle("score")}
                  >
                    Net
                    <ArrowUpDown className="h-3 w-3 opacity-50" />
                  </button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((item, i) => (
                <TableRow key={item.ticker}>
                  <TableCell className="text-muted-foreground">
                    {i + 1}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-semibold tabular-nums">
                        {item.ticker}
                      </span>
                      <span className="truncate text-[11px] text-muted-foreground">
                        {item.name}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs text-muted-foreground">
                    {item.articles}
                  </TableCell>
                  <TableCell className="text-right">
                    <SentimentBadge
                      label={
                        item.score > 0.15
                          ? "positive"
                          : item.score < -0.15
                            ? "negative"
                            : "neutral"
                      }
                      score={(item.score + 1) / 2}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export default function TrendAnalysisPage() {
  const [range, setRange] = useState<"7" | "30" | "90">("30");
  const days = Number(range);

  const trends = useApi(() => getTrends(days), [days]);
  const companiesApi = useApi(() => getCompanies(), []);

  const companyTickers = useMemo(
    () => (companiesApi.data ?? []).slice(0, 10),
    [companiesApi.data],
  );

  const companyHistories = useApi(
    () =>
      Promise.all(
        companyTickers.map((c) =>
          getSentimentHistory(c.ticker, days).then(
            (hist) => [c.ticker, hist] as const,
          ),
        ),
      ).then((entries) => new Map(entries)),
    [companyTickers, days],
  );

  const chartData = useMemo(
    () => (trends.data ? toChartData(trends.data) : []),
    [trends.data],
  );
  const ticks = useMemo(
    () => pickXAxisTicks(chartData, "dateLabel", 6),
    [chartData],
  );

  const scores = useMemo(
    () =>
      rankCompanies(
        companiesApi.data ?? [],
        companyHistories.data ?? new Map(),
      ),
    [companiesApi.data, companyHistories.data],
  );

  const loading =
    trends.loading || companiesApi.loading || companyHistories.loading;
  const error = trends.error || companiesApi.error;

  return (
    <div className="mx-auto w-full max-w-[1200px] px-4 py-6 md:px-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <TrendingUp className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              Trend analysis
            </h1>
            <p className="text-xs text-muted-foreground">
              Market-wide sentiment momentum and top movers
            </p>
          </div>
        </div>

        <ToggleGroup
          type="single"
          value={range}
          onValueChange={(v) => v && setRange(v as typeof range)}
          size="sm"
          variant="outline"
          aria-label="Date range"
        >
          <ToggleGroupItem value="7">7d</ToggleGroupItem>
          <ToggleGroupItem value="30">30d</ToggleGroupItem>
          <ToggleGroupItem value="90">90d</ToggleGroupItem>
        </ToggleGroup>
      </header>

      {loading && <LoadingSpinner message="Analysing market trends…" />}
      {error && (
        <ErrorMessage message={error} onRetry={() => trends.refetch()} />
      )}

      {!loading && !error && (
        <div className="space-y-6">
          {chartData.length === 0 ? (
            <Card>
              <CardContent className="py-14">
                <EmptyState
                  icon={TrendingUp}
                  title="No trend data available"
                  description="Run the collection pipeline (docker compose celery worker) to populate this chart."
                  action={
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => trends.refetch()}
                    >
                      Refresh
                    </Button>
                  }
                />
              </CardContent>
            </Card>
          ) : (
            <ChartCard
              title="Overall market sentiment"
              subtitle="Rolling ratios across every tracked ticker"
              badge={`${days}d`}
            >
              <ResponsiveContainer width="100%" height={320}>
                <ComposedChart
                  data={chartData}
                  margin={{ top: 8, right: 8, bottom: 0, left: -8 }}
                >
                  <defs>
                    <linearGradient id="mktGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="0%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.25}
                      />
                      <stop
                        offset="100%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0}
                      />
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
                  <Tooltip content={<TrendTooltipBody />} />
                  <Area
                    yAxisId="left"
                    type="monotone"
                    dataKey="score"
                    fill="url(#mktGrad)"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    name="score"
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
                </ComposedChart>
              </ResponsiveContainer>
            </ChartCard>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <RankTable
              title="Most positive"
              items={scores}
              variant="positive"
            />
            <RankTable
              title="Most negative"
              items={scores}
              variant="negative"
            />
          </div>
        </div>
      )}
    </div>
  );
}
