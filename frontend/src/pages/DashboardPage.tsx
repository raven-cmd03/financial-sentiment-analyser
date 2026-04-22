import {
  BarChart3,
  Newspaper,
  TrendingUp,
  TrendingDown,
  Activity,
  Sparkles,
} from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useApi } from "@/hooks/useApi";
import { getTrends, getTrendingTickers } from "@/api/client";
import DashboardLayout from "@/components/Dashboard/DashboardLayout";
import CompanySelector from "@/components/CompanySelector/CompanySelector";
import SentimentChart from "@/components/SentimentChart/SentimentChart";
import CorrelationTable from "@/components/CorrelationTable/CorrelationTable";
import KpiCard from "@/components/Dashboard/KpiCard";
import EmptyState from "@/components/common/EmptyState";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function KpiSkeleton() {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-3 w-24" />
        </div>
      </CardContent>
    </Card>
  );
}

function KpiStrip() {
  const trends = useApi(() => getTrends(7), []);
  const trending = useApi(() => getTrendingTickers(), []);

  if (trends.loading) {
    return (
      <section
        aria-label="Key metrics"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <KpiSkeleton key={i} />
        ))}
      </section>
    );
  }

  const series = trends.data ?? [];
  const today = series[series.length - 1];
  const articlesToday = today?.article_count ?? 0;
  const avgPositive = today ? today.positive_ratio : 0;
  const netScore = today ? today.sentiment_score : 0;

  const topMover = trending.data?.[0];
  const topMoverTone = (topMover?.buzz_score ?? 0) >= 0 ? "positive" : "negative";
  const topMoverFallback =
    series.length > 0
      ? series
          .slice()
          .sort((a, b) => b.article_count - a.article_count)[0]
      : null;

  return (
    <section
      aria-label="Key metrics"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
    >
      <KpiCard
        label="Articles (latest)"
        value={articlesToday.toLocaleString()}
        sublabel={today?.date ?? "—"}
        icon={<Newspaper className="h-4 w-4" />}
        tone="primary"
        spark={series.map((p) => p.article_count)}
      />
      <KpiCard
        label="Avg Positive"
        value={`${(avgPositive * 100).toFixed(1)}%`}
        sublabel="Last session"
        icon={<TrendingUp className="h-4 w-4" />}
        tone="positive"
        spark={series.map((p) => p.positive_ratio)}
      />
      <KpiCard
        label="Net Sentiment"
        value={`${netScore >= 0 ? "+" : ""}${(netScore * 100).toFixed(1)}`}
        sublabel="Positive − Negative"
        icon={
          netScore >= 0 ? (
            <TrendingUp className="h-4 w-4" />
          ) : (
            <TrendingDown className="h-4 w-4" />
          )
        }
        tone={netScore >= 0 ? "positive" : "negative"}
        spark={series.map((p) => p.sentiment_score)}
      />
      {topMover ? (
        <KpiCard
          label="Top Mover"
          value={topMover.ticker_symbol}
          sublabel={`buzz ${(topMover.buzz_score ?? 0).toFixed(1)}`}
          icon={<Activity className="h-4 w-4" />}
          tone={topMoverTone}
        />
      ) : topMoverFallback ? (
        <KpiCard
          label="Most Coverage"
          value={`${topMoverFallback.article_count} art.`}
          sublabel={topMoverFallback.date}
          icon={<Activity className="h-4 w-4" />}
          tone="neutral"
        />
      ) : (
        <KpiCard
          label="Top Mover"
          value="—"
          sublabel="Waiting for social data"
          icon={<Activity className="h-4 w-4" />}
          tone="neutral"
        />
      )}
    </section>
  );
}

function WelcomePrompt() {
  return (
    <Card>
      <CardContent className="py-14">
        <EmptyState
          icon={BarChart3}
          title="Pick a company to get started"
          description="Use the sidebar (or press ⌘K) to select a ticker. You'll see sentiment history, market correlations, and recent news."
        />
      </CardContent>
    </Card>
  );
}

function DashboardMain() {
  const { selectedCompany } = useAppContext();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Sparkles className="h-4 w-4" />
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            Market overview
          </h1>
          <p className="text-xs text-muted-foreground">
            Sentiment signals from news, RSS, and social across tracked tickers.
          </p>
        </div>
      </div>

      <KpiStrip />

      {selectedCompany ? (
        <div className="flex flex-col gap-5">
          <SentimentChart ticker={selectedCompany} />
          <CorrelationTable ticker={selectedCompany} />
        </div>
      ) : (
        <WelcomePrompt />
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <DashboardLayout sidebar={<CompanySelector />} main={<DashboardMain />} />
  );
}
