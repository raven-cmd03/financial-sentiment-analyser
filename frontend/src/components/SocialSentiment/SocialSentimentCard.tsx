import { MessageSquare } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { getSocialSentiment } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import SentimentBadge from "@/components/common/SentimentBadge";
import EmptyState from "@/components/common/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import type { SocialSentiment as SocialSentimentType } from "@/types";

interface SocialSentimentCardProps {
  ticker: string;
  /** Optional preloaded row — pass this to avoid a duplicate fetch when the
   * caller already has a `SocialSentiment` object in hand (e.g. the detail
   * page fetched the full company payload). When omitted the card fetches
   * its own data from `/api/social/{ticker}`. */
  preloaded?: SocialSentimentType | null;
}

function formatFetchedAt(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
}

/**
 * Compact social-sentiment card used on the dashboard and on the per-company
 * detail page. Shows buzz score, post volume, bullish/bearish split and the
 * snapshot freshness.
 */
export default function SocialSentimentCard({
  ticker,
  preloaded,
}: SocialSentimentCardProps) {
  // Only hit the API when the caller didn't pass data in — avoids refetching
  // the same row the CompanyDetailPage already has.
  const shouldFetch = preloaded === undefined;
  const fetched = useApi(
    () =>
      shouldFetch
        ? getSocialSentiment(ticker)
        : Promise.resolve<SocialSentimentType | null>(null),
    [ticker, shouldFetch],
  );

  const item: SocialSentimentType | null = shouldFetch
    ? fetched.data ?? null
    : preloaded ?? null;
  const loading = shouldFetch && fetched.loading;

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0 pb-3">
        <MessageSquare className="h-4 w-4 text-primary" aria-hidden="true" />
        <CardTitle className="text-sm">
          Social sentiment · {ticker.toUpperCase()}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <SocialSkeleton />
        ) : item ? (
          <SocialBody item={item} />
        ) : (
          <EmptyState
            icon={MessageSquare}
            title="No social data yet"
            description={`Social metrics haven't been collected for ${ticker.toUpperCase()}.`}
          />
        )}
      </CardContent>
    </Card>
  );
}

function SocialSkeleton() {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-3 w-28" />
        </div>
        <Skeleton className="h-5 w-14 rounded-full" />
      </div>
      <Skeleton className="h-1.5 w-full rounded-full" />
      <div className="flex justify-between">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

function SocialBody({ item }: { item: SocialSentimentType }) {
  const bullish = item.bullish_ratio ?? 0;
  const bearish = item.bearish_ratio ?? 0;
  // 10-point deadband so a razor-thin bullish edge doesn't flip the badge
  // every refresh — matches the threshold used on the detail page.
  const label: "positive" | "negative" | "neutral" =
    bullish > bearish + 0.1
      ? "positive"
      : bearish > bullish + 0.1
        ? "negative"
        : "neutral";
  const confidence = Math.max(bullish, bearish);
  const fetchedAt = formatFetchedAt(item.fetched_at);

  return (
    <div className="rounded-md border border-border bg-background px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">X / Social</p>
          <p className="text-xs text-muted-foreground">
            {(item.post_volume ?? 0).toLocaleString()} posts · buzz{" "}
            {(item.buzz_score ?? 0).toFixed(1)}
          </p>
        </div>
        <SentimentBadge label={label} confidence={confidence} />
      </div>
      <div className="mt-3 flex h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-positive transition-[width] duration-300"
          style={{ width: `${(bullish * 100).toFixed(0)}%` }}
          aria-hidden="true"
        />
        <div
          className="h-full bg-negative transition-[width] duration-300"
          style={{ width: `${(bearish * 100).toFixed(0)}%` }}
          aria-hidden="true"
        />
      </div>
      <div className="mt-2 flex justify-between text-xs text-muted-foreground">
        <span>Bullish {(bullish * 100).toFixed(0)}%</span>
        <span>Bearish {(bearish * 100).toFixed(0)}%</span>
      </div>
      {fetchedAt && (
        <p className="mt-2 text-[10px] text-muted-foreground">
          Updated {fetchedAt}
        </p>
      )}
    </div>
  );
}
