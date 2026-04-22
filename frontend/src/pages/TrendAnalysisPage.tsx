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
} from "recharts";
import { format, parseISO } from "date-fns";
import { TrendingUp, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { getTrends, getCompanies, getSentimentHistory } from "@/api/client";
import Navbar from "@/components/common/Navbar";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import SentimentBadge from "@/components/common/SentimentBadge";
import type { Company, TrendData } from "@/types";

interface ChartPoint {
  date: string;
  dateLabel: string;
  sentiment: number;
  positive: number;
  negative: number;
  articles: number;
}

function toChartData(raw: TrendData[]): ChartPoint[] {
  return raw.map((d) => ({
    date: d.date,
    dateLabel: format(parseISO(d.date), "MMM d"),
    sentiment: d.sentiment_score,
    positive: d.positive_ratio,
    negative: d.negative_ratio,
    articles: d.article_count,
  }));
}

interface CompanyRank {
  ticker: string;
  name: string;
  score: number;
}

function rankCompanies(
  companies: Company[],
  histories: Map<string, TrendData[]>,
): { top: CompanyRank[]; bottom: CompanyRank[] } {
  const scores: CompanyRank[] = [];

  for (const c of companies) {
    const hist = histories.get(c.ticker);
    if (!hist || hist.length === 0) continue;
    const avg =
      hist.reduce((sum, d) => sum + d.sentiment_score, 0) / hist.length;
    scores.push({ ticker: c.ticker, name: c.name, score: avg });
  }

  scores.sort((a, b) => b.score - a.score);
  return {
    top: scores.slice(0, 5),
    bottom: scores.slice(-5).reverse(),
  };
}

interface TooltipEntry {
  name: string;
  value: number;
  color: string;
}

interface TrendTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
}

function TrendTooltip({ active, payload, label }: TrendTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-3 shadow-2xl">
      <p className="mb-1.5 text-[11px] font-semibold text-[var(--color-text-primary)]">
        {label}
      </p>
      {payload.map((entry) => (
        <div
          key={entry.name}
          className="flex items-center justify-between gap-6 py-0.5 text-[11px]"
        >
          <span className="capitalize" style={{ color: entry.color }}>
            {entry.name}
          </span>
          <span className="font-mono text-[var(--color-text-primary)]">
            {entry.name === "articles"
              ? entry.value
              : `${(entry.value * 100).toFixed(1)}%`}
          </span>
        </div>
      ))}
    </div>
  );
}

function RankTable({
  title,
  items,
  variant,
}: {
  title: string;
  items: CompanyRank[];
  variant: "positive" | "negative";
}) {
  const icon =
    variant === "positive" ? (
      <ArrowUpRight className="h-4 w-4 text-[var(--color-positive)]" />
    ) : (
      <ArrowDownRight className="h-4 w-4 text-[var(--color-negative)]" />
    );

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
      <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-3">
        {icon}
        <h3 className="text-[13px] font-semibold text-[var(--color-text-primary)]">
          {title}
        </h3>
      </div>
      <div className="divide-y divide-[var(--color-border-subtle)]">
        {items.length === 0 ? (
          <p className="px-4 py-6 text-center text-[12px] text-[var(--color-text-muted)]">
            No data available
          </p>
        ) : (
          items.map((item, i) => (
            <div
              key={item.ticker}
              className="flex items-center justify-between px-4 py-2.5 transition-colors hover:bg-[var(--color-bg-tertiary)]/30"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-5 w-5 items-center justify-center rounded-md bg-[var(--color-bg-tertiary)]/50 text-[10px] font-bold text-[var(--color-text-muted)]">
                  {i + 1}
                </span>
                <div>
                  <p className="text-[13px] font-semibold text-[var(--color-text-primary)]">
                    {item.ticker}
                  </p>
                  <p className="text-[11px] text-[var(--color-text-muted)]">
                    {item.name}
                  </p>
                </div>
              </div>
              <SentimentBadge
                label={
                  item.score > 0.55
                    ? "positive"
                    : item.score < 0.45
                      ? "negative"
                      : "neutral"
                }
                confidence={item.score}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function TrendAnalysisPage() {
  const trends = useApi(() => getTrends(30), []);
  const companiesApi = useApi(() => getCompanies(), []);

  const companyTickers = useMemo(
    () => (companiesApi.data ?? []).slice(0, 10),
    [companiesApi.data],
  );

  const companyHistories = useApi(
    () =>
      Promise.all(
        companyTickers.map((c) =>
          getSentimentHistory(c.ticker, 30).then(
            (hist) => [c.ticker, hist] as const,
          ),
        ),
      ).then((entries) => new Map(entries)),
    [companyTickers],
  );

  const chartData = useMemo(
    () => (trends.data ? toChartData(trends.data) : []),
    [trends.data],
  );

  const { top, bottom } = useMemo(
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
    <div className="flex min-h-screen flex-col bg-[var(--color-bg-primary)]">
      <Navbar />

      <div className="mx-auto w-full max-w-[1200px] flex-1 px-5 py-4">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--color-accent)]/10">
            <TrendingUp className="h-4.5 w-4.5 text-[var(--color-accent)]" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">
              Trend Analysis
            </h1>
            <p className="text-[12px] text-[var(--color-text-muted)]">
              Market-wide sentiment trends and top movers
            </p>
          </div>
        </div>

        {loading && <LoadingSpinner message="Analyzing market trends…" />}
        {error && <ErrorMessage message={error} />}

        {!loading && !error && (
          <>
            <div className="mb-5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
              <h3 className="mb-4 text-sm font-semibold text-[var(--color-text-primary)]">
                Overall Market Sentiment
                <span className="ml-2 rounded-full bg-[var(--color-bg-tertiary)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-text-muted)]">
                  30d
                </span>
              </h3>
              {chartData.length === 0 ? (
                <p className="py-12 text-center text-[13px] text-[var(--color-text-muted)]">
                  No trend data available yet.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={chartData}>
                    <defs>
                      <linearGradient id="mktGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6366f1" stopOpacity={0.15} />
                        <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                    <XAxis
                      dataKey="dateLabel"
                      tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 1]}
                      tick={{ fontSize: 10, fill: "var(--color-text-muted)" }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                    />
                    <Tooltip content={<TrendTooltip />} />
                    <Area type="monotone" dataKey="sentiment" fill="url(#mktGrad)" stroke="none" name="sentiment" />
                    <Line type="monotone" dataKey="positive" stroke="#34d399" strokeWidth={2} dot={false} name="positive" />
                    <Line type="monotone" dataKey="negative" stroke="#f87171" strokeWidth={2} dot={false} name="negative" />
                    <Line type="monotone" dataKey="sentiment" stroke="#6366f1" strokeWidth={2} dot={false} name="sentiment" />
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <RankTable title="Most Positive" items={top} variant="positive" />
              <RankTable title="Most Negative" items={bottom} variant="negative" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
