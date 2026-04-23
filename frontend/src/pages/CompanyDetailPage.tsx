import { useParams, Link } from "react-router-dom";
import {
  Building2,
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  Newspaper,
  Activity,
} from "lucide-react";
import { useApi } from "@/hooks/useApi";
import {
  getCompany,
  getCompanySentiment,
  getNewsByTicker,
  getSocialSentiment,
} from "@/api/client";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import SentimentBadge from "@/components/common/SentimentBadge";
import EmptyState from "@/components/common/EmptyState";
import SentimentChart from "@/components/SentimentChart/SentimentChart";
import PriceChart from "@/components/PriceChart/PriceChart";
import CorrelationTable from "@/components/CorrelationTable/CorrelationTable";
import SocialSentimentCard from "@/components/SocialSentiment/SocialSentimentCard";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

function TrendIcon({ trend, className }: { trend: string; className?: string }) {
  const cls = className ?? "h-4 w-4";
  if (trend === "up")
    return <TrendingUp className={cn(cls, "text-positive")} aria-hidden="true" />;
  if (trend === "down")
    return <TrendingDown className={cn(cls, "text-negative")} aria-hidden="true" />;
  return <Minus className={cn(cls, "text-muted-foreground")} aria-hidden="true" />;
}

interface HeroKpiProps {
  label: string;
  value: string;
  sublabel?: string;
  tone?: "positive" | "negative" | "neutral" | "accent";
  icon?: React.ReactNode;
}

function HeroKpi({ label, value, sublabel, tone = "accent", icon }: HeroKpiProps) {
  const toneClasses = {
    positive: "bg-positive/10 text-positive",
    negative: "bg-negative/10 text-negative",
    neutral: "bg-muted text-muted-foreground",
    accent: "bg-primary/10 text-primary",
  };
  const textClass = {
    positive: "text-positive",
    negative: "text-negative",
    neutral: "text-foreground",
    accent: "text-foreground",
  };
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
      {icon && (
        <div
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-md",
            toneClasses[tone],
          )}
          aria-hidden="true"
        >
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p className={cn("text-lg font-semibold", textClass[tone])}>{value}</p>
        {sublabel && (
          <p className="text-[11px] text-muted-foreground">{sublabel}</p>
        )}
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
    <div className="mx-auto w-full max-w-7xl p-6">
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-primary"
      >
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
        Back to Dashboard
      </Link>

      {isLoading && <LoadingSpinner message="Loading company data…" />}
      {firstError && <ErrorMessage message={firstError} />}

      {!isLoading && !firstError && company.data && (
        <>
          <Card className="mb-6">
            <CardContent className="p-6">
              <div className="flex flex-wrap items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                  <Building2 className="h-5 w-5 text-primary" aria-hidden="true" />
                </div>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-2xl font-semibold tracking-tight text-foreground">
                      {company.data.name}
                    </h1>
                    <Badge variant="secondary">{company.data.ticker}</Badge>
                    {sentiment.data && <SentimentBadge label={sentimentLabel} />}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {company.data.sector ?? "—"} ·{" "}
                    {company.data.industry ?? "—"}
                  </p>
                </div>
              </div>

              {sentiment.data && (
                <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
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
                    value={`${(sentiment.data.average_positive * 100).toFixed(0)}%`}
                    sublabel="Avg probability"
                    tone="positive"
                    icon={<TrendingUp className="h-4 w-4" />}
                  />
                  <HeroKpi
                    label="Negative"
                    value={`${(sentiment.data.average_negative * 100).toFixed(0)}%`}
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
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="flex flex-col gap-6 lg:col-span-2">
              <Tabs defaultValue="sentiment">
                <TabsList>
                  <TabsTrigger value="sentiment">Sentiment</TabsTrigger>
                  <TabsTrigger value="price">Price</TabsTrigger>
                  <TabsTrigger value="correlation">Correlation</TabsTrigger>
                </TabsList>
                <TabsContent value="sentiment" className="mt-4">
                  <SentimentChart ticker={safeTicker} />
                </TabsContent>
                <TabsContent value="price" className="mt-4">
                  <PriceChart ticker={safeTicker} />
                </TabsContent>
                <TabsContent value="correlation" className="mt-4">
                  <CorrelationTable ticker={safeTicker} />
                </TabsContent>
              </Tabs>
            </div>

            <aside className="flex flex-col gap-6">
              <SocialSentimentCard
                ticker={safeTicker}
                preloaded={socialData}
              />

              <Card>
                <CardHeader className="flex-row items-center gap-2 space-y-0 pb-3">
                  <Activity
                    className="h-4 w-4 text-primary"
                    aria-hidden="true"
                  />
                  <CardTitle className="text-sm">Recent news</CardTitle>
                </CardHeader>
                <CardContent>
                  {articles.length > 0 ? (
                    <ul className="flex flex-col gap-2">
                      {articles.map((article) => (
                        <li key={article.article_id}>
                          <a
                            href={article.url ?? "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group flex flex-col gap-1 rounded-md border border-border bg-background p-3 transition-all hover:border-primary/40"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="line-clamp-2 text-xs font-medium leading-snug text-foreground transition-colors group-hover:text-primary">
                                {article.title}
                              </p>
                              <ExternalLink
                                className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                                aria-hidden="true"
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-muted-foreground">
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
                    <EmptyState
                      icon={Newspaper}
                      title="No recent articles"
                      description="No articles collected for this ticker yet."
                    />
                  )}
                </CardContent>
              </Card>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
