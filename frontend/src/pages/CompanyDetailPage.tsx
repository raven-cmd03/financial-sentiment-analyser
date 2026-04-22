import { useParams, Link } from "react-router-dom";
import {
  Building2,
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  Newspaper,
  MessageSquare,
  Activity,
} from "lucide-react";
import { useApi } from "@/hooks/useApi";
import {
  getCompany,
  getCompanySentiment,
  getNewsByTicker,
  getSocialSentiment,
} from "@/api/client";
import Navbar from "@/components/common/Navbar";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import SentimentBadge from "@/components/common/SentimentBadge";
import SentimentChart from "@/components/SentimentChart/SentimentChart";
import CorrelationTable from "@/components/CorrelationTable/CorrelationTable";
import type { SocialSentiment as SocialSentimentType } from "@/types";

function TrendIcon({ trend, className }: { trend: string; className?: string }) {
  const cls = className ?? "h-4 w-4";
  if (trend === "up")
    return <TrendingUp className={`${cls} text-[var(--color-positive)]`} aria-hidden="true" />;
  if (trend === "down")
    return <TrendingDown className={`${cls} text-[var(--color-negative)]`} aria-hidden="true" />;
  return <Minus className={`${cls} text-[var(--color-text-muted)]`} aria-hidden="true" />;
}

interface HeroKpiProps {
  label: string;
  value: string;
  sublabel?: string;
  tone?: "positive" | "negative" | "neutral" | "accent";
  icon?: React.ReactNode;
}

function HeroKpi({ label, value, sublabel, tone = "accent", icon }: HeroKpiProps) {
  const toneColor =
    tone === "positive"
      ? "var(--color-positive)"
      : tone === "negative"
        ? "var(--color-negative)"
        : tone === "neutral"
          ? "var(--color-text-muted)"
          : "var(--color-accent)";
  return (
    <div className="flex items-center gap-3 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-4 py-2.5">
      {icon && (
        <div
          className="flex h-8 w-8 items-center justify-center rounded-md"
          style={{ backgroundColor: `${toneColor}1a`, color: toneColor }}
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
      <div>
        <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)]">
          {label}
        </p>
        <p className="text-[15px] font-semibold" style={{ color: toneColor }}>
          {value}
        </p>
        {sublabel && (
          <p className="text-[11px] text-[var(--color-text-muted)]">{sublabel}</p>
        )}
      </div>
    </div>
  );
}

function SocialCard({ item }: { item: SocialSentimentType }) {
  const bullish = item.bullish_ratio ?? 0;
  const bearish = item.bearish_ratio ?? 0;
  const label: "positive" | "negative" | "neutral" =
    bullish > bearish + 0.1
      ? "positive"
      : bearish > bullish + 0.1
        ? "negative"
        : "neutral";
  const confidence = Math.max(bullish, bearish);
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3.5 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[13px] font-medium text-[var(--color-text-primary)]">
            X / Social
          </p>
          <p className="text-[11px] text-[var(--color-text-muted)]">
            {item.post_volume ?? 0} posts · buzz{" "}
            {(item.buzz_score ?? 0).toFixed(1)}
          </p>
        </div>
        <SentimentBadge label={label} confidence={confidence} />
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-bg-tertiary)]">
        <div
          className="h-full bg-[var(--color-positive)]"
          style={{ width: `${(bullish * 100).toFixed(0)}%` }}
          aria-hidden="true"
        />
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-[var(--color-text-muted)]">
        <span>Bullish {(bullish * 100).toFixed(0)}%</span>
        <span>Bearish {(bearish * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}

export default function CompanyDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const safeTicker = ticker ?? "";

  const company = useApi(() => getCompany(safeTicker), [safeTicker]);
  const sentiment = useApi(() => getCompanySentiment(safeTicker), [safeTicker]);
  const news = useApi(
    () => getNewsByTicker(safeTicker, { limit: 10 }),
    [safeTicker],
  );
  const social = useApi(() => getSocialSentiment(safeTicker), [safeTicker]);

  const isLoading =
    company.loading || sentiment.loading || news.loading || social.loading;
  const firstError = company.error || sentiment.error || news.error;

  const articles = news.data ?? [];
  const socialData = social.data ?? null;
  const sentimentLabel: "positive" | "negative" | "neutral" =
    sentiment.data?.overall_sentiment === "positive" ||
    sentiment.data?.overall_sentiment === "negative" ||
    sentiment.data?.overall_sentiment === "neutral"
      ? sentiment.data.overall_sentiment
      : "neutral";

  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-bg-primary)]">
      <Navbar />

      <div className="mx-auto w-full max-w-[1200px] flex-1 px-5 py-4">
        <Link
          to="/"
          className="mb-4 inline-flex items-center gap-1.5 text-[12px] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-accent)]"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Back to Dashboard
        </Link>

        {isLoading && <LoadingSpinner message="Loading company data…" />}
        {firstError && <ErrorMessage message={firstError} />}

        {!isLoading && !firstError && company.data && (
          <>
            <header className="mb-5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
              <div className="flex flex-wrap items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--color-accent)]/10">
                  <Building2 className="h-5 w-5 text-[var(--color-accent)]" aria-hidden="true" />
                </div>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
                      {company.data.name}
                    </h1>
                    <span className="rounded-md bg-[var(--color-bg-tertiary)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-text-secondary)]">
                      {company.data.ticker}
                    </span>
                    {sentiment.data && (
                      <SentimentBadge label={sentimentLabel} />
                    )}
                  </div>
                  <p className="mt-1 text-[12px] text-[var(--color-text-muted)]">
                    {company.data.sector ?? "—"} ·{" "}
                    {company.data.industry ?? "—"}
                  </p>
                </div>
              </div>

              {sentiment.data && (
                <div className="mt-4 grid grid-cols-2 gap-2.5 md:grid-cols-4">
                  <HeroKpi
                    label="Overall"
                    value={`${sentiment.data.overall_score >= 0 ? "+" : ""}${(
                      sentiment.data.overall_score * 100
                    ).toFixed(1)}`}
                    sublabel="Net sentiment"
                    tone={
                      sentiment.data.overall_score >= 0 ? "positive" : "negative"
                    }
                    icon={<TrendIcon trend={sentiment.data.trending} />}
                  />
                  <HeroKpi
                    label="Positive"
                    value={`${(sentiment.data.average_positive * 100).toFixed(
                      0,
                    )}%`}
                    sublabel="Avg probability"
                    tone="positive"
                    icon={<TrendingUp className="h-4 w-4" />}
                  />
                  <HeroKpi
                    label="Negative"
                    value={`${(sentiment.data.average_negative * 100).toFixed(
                      0,
                    )}%`}
                    sublabel="Avg probability"
                    tone="negative"
                    icon={<TrendingDown className="h-4 w-4" />}
                  />
                  <HeroKpi
                    label="Articles"
                    value={sentiment.data.article_count.toLocaleString()}
                    sublabel="Last 30 days"
                    tone="accent"
                    icon={<Newspaper className="h-4 w-4" />}
                  />
                </div>
              )}
            </header>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="flex flex-col gap-5 lg:col-span-2">
                <section aria-label="Sentiment history">
                  <SentimentChart ticker={safeTicker} />
                </section>
                <section aria-label="Correlations">
                  <CorrelationTable ticker={safeTicker} />
                </section>
              </div>

              <aside className="flex flex-col gap-5">
                <section
                  aria-label="Social sentiment"
                  className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4"
                >
                  <h3 className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-[var(--color-text-primary)]">
                    <MessageSquare className="h-3.5 w-3.5 text-[var(--color-accent)]" aria-hidden="true" />
                    Social Sentiment
                  </h3>
                  {socialData ? (
                    <SocialCard item={socialData} />
                  ) : (
                    <p className="rounded-[var(--radius-md)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-4 text-center text-[12px] text-[var(--color-text-muted)]">
                      No social data yet.
                    </p>
                  )}
                </section>

                <section
                  aria-label="Recent news"
                  className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4"
                >
                  <h3 className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-[var(--color-text-primary)]">
                    <Activity className="h-3.5 w-3.5 text-[var(--color-accent)]" aria-hidden="true" />
                    Recent News
                  </h3>
                  {articles.length > 0 ? (
                    <ul className="flex flex-col gap-2">
                      {articles.map((article) => (
                        <li key={article.article_id}>
                          <a
                            href={article.url ?? "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group flex flex-col gap-1 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-primary)] p-2.5 transition-all duration-150 hover:border-[var(--color-accent)]/30"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="line-clamp-2 text-[12px] font-medium leading-snug text-[var(--color-text-primary)] transition-colors group-hover:text-[var(--color-accent)]">
                                {article.title}
                              </p>
                              <ExternalLink
                                className="mt-0.5 h-3 w-3 shrink-0 text-[var(--color-text-muted)] opacity-0 transition-opacity group-hover:opacity-100"
                                aria-hidden="true"
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-[var(--color-text-muted)]">
                                {article.source}
                              </span>
                              {article.sentiment && (
                                <SentimentBadge
                                  label={
                                    (article.sentiment.sentiment_label as
                                      | "positive"
                                      | "negative"
                                      | "neutral") || "neutral"
                                  }
                                  confidence={article.sentiment.confidence}
                                />
                              )}
                            </div>
                          </a>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="rounded-[var(--radius-md)] border border-dashed border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-4 text-center text-[12px] text-[var(--color-text-muted)]">
                      No recent articles for this ticker.
                    </p>
                  )}
                </section>
              </aside>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
