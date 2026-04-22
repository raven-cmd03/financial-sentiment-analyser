import { BarChart3, Newspaper, TrendingUp, TrendingDown, Activity } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { useApi } from "@/hooks/useApi";
import { getTrends, getTrendingTickers } from "@/api/client";
import DashboardLayout from "@/components/Dashboard/DashboardLayout";
import CompanySelector from "@/components/CompanySelector/CompanySelector";
import SentimentChart from "@/components/SentimentChart/SentimentChart";
import CorrelationTable from "@/components/CorrelationTable/CorrelationTable";

interface KpiProps {
  label: string;
  value: string;
  sublabel?: string;
  icon: React.ReactNode;
  tone?: "accent" | "positive" | "negative" | "neutral";
}

function KpiCard({ label, value, sublabel, icon, tone = "accent" }: KpiProps) {
  const toneColor =
    tone === "positive"
      ? "var(--color-positive)"
      : tone === "negative"
        ? "var(--color-negative)"
        : tone === "neutral"
          ? "var(--color-text-muted)"
          : "var(--color-accent)";
  return (
    <div className="flex items-start gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-4 py-3">
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: `${toneColor}1a`, color: toneColor }}
        aria-hidden="true"
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[11px] uppercase tracking-wide text-[var(--color-text-muted)]">
          {label}
        </p>
        <p
          className="truncate text-[18px] font-semibold leading-snug"
          style={{ color: toneColor }}
        >
          {value}
        </p>
        {sublabel && (
          <p className="truncate text-[11px] text-[var(--color-text-muted)]">
            {sublabel}
          </p>
        )}
      </div>
    </div>
  );
}

function KpiStrip() {
  const trends = useApi(() => getTrends(7), []);
  const trending = useApi(() => getTrendingTickers(), []);

  const today = trends.data?.[trends.data.length - 1];
  const articlesToday = today?.article_count ?? 0;
  const avgPositive = today ? today.positive_ratio : 0;
  const netScore = today ? today.sentiment_score : 0;

  const topMover = trending.data?.[0];
  const topMoverTone: KpiProps["tone"] =
    (topMover?.buzz_score ?? 0) >= 0 ? "positive" : "negative";

  return (
    <section
      aria-label="Key metrics"
      className="grid grid-cols-2 gap-3 sm:grid-cols-4"
    >
      <KpiCard
        label="Articles (7d latest)"
        value={articlesToday.toLocaleString()}
        sublabel={today?.date ?? "—"}
        icon={<Newspaper className="h-4 w-4" />}
        tone="accent"
      />
      <KpiCard
        label="Avg Positive"
        value={`${(avgPositive * 100).toFixed(1)}%`}
        sublabel="Last session"
        icon={<TrendingUp className="h-4 w-4" />}
        tone="positive"
      />
      <KpiCard
        label="Net Sentiment"
        value={`${netScore >= 0 ? "+" : ""}${(netScore * 100).toFixed(1)}`}
        sublabel="Positive − Negative"
        icon={netScore >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
        tone={netScore >= 0 ? "positive" : "negative"}
      />
      <KpiCard
        label="Top Mover"
        value={topMover?.ticker_symbol ?? "—"}
        sublabel={
          topMover
            ? `buzz ${(topMover.buzz_score ?? 0).toFixed(1)}`
            : "No data yet"
        }
        icon={<Activity className="h-4 w-4" />}
        tone={topMoverTone}
      />
    </section>
  );
}

function WelcomePrompt() {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-24 text-center">
      <div className="rounded-2xl bg-[var(--color-accent)]/10 p-4">
        <BarChart3 className="h-10 w-10 text-[var(--color-accent)]" aria-hidden="true" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
          Welcome to FinSentiment
        </h2>
        <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-[var(--color-text-muted)]">
          Select a company from the sidebar to view sentiment analysis,
          historical trends, and market correlation data.
        </p>
      </div>
    </div>
  );
}

function DashboardMain() {
  const { selectedCompany } = useAppContext();

  return (
    <div className="flex flex-col gap-5">
      <KpiStrip />
      {selectedCompany ? (
        <>
          <SentimentChart ticker={selectedCompany} />
          <CorrelationTable ticker={selectedCompany} />
        </>
      ) : (
        <WelcomePrompt />
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <DashboardLayout
      sidebar={<CompanySelector />}
      main={<DashboardMain />}
    />
  );
}
