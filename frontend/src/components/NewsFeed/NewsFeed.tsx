import { useState, useCallback, useEffect } from "react";
import { formatDistanceToNow } from "date-fns";
import { ExternalLink, Loader2 } from "lucide-react";
import { getNews, getNewsByTicker } from "@/api/client";
import { useAppContext } from "@/context/AppContext";
import SentimentBadge from "@/components/common/SentimentBadge";
import type { NewsArticle } from "@/types";

interface NewsFeedProps {
  ticker?: string;
}

const PAGE_SIZE = 10;

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
      <div className="h-4 w-3/4 rounded bg-[var(--color-bg-tertiary)]" />
      <div className="mt-3 flex gap-2">
        <div className="h-3 w-16 rounded bg-[var(--color-bg-tertiary)]" />
        <div className="h-3 w-20 rounded bg-[var(--color-bg-tertiary)]" />
      </div>
      <div className="mt-3 space-y-2">
        <div className="h-3 w-full rounded bg-[var(--color-bg-tertiary)]" />
        <div className="h-3 w-5/6 rounded bg-[var(--color-bg-tertiary)]" />
      </div>
    </div>
  );
}

export default function NewsFeed({ ticker }: NewsFeedProps) {
  const { filters } = useAppContext();
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchArticles = useCallback(
    async (nextOffset: number, append: boolean) => {
      if (append) setLoadingMore(true);
      else setLoading(true);
      setError(null);

      try {
        const params = {
          limit: PAGE_SIZE,
          offset: nextOffset,
          sentiment: filters.sentiment !== "all" ? filters.sentiment : undefined,
          source: filters.source !== "all" ? filters.source : undefined,
        };

        const result = ticker
          ? await getNewsByTicker(ticker, params)
          : await getNews(params);

        setArticles((prev) => (append ? [...prev, ...result] : result));
        setHasMore(result.length === PAGE_SIZE);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load news");
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [ticker, filters],
  );

  useEffect(() => {
    setOffset(0);
    fetchArticles(0, false);
  }, [fetchArticles]);

  const handleLoadMore = () => {
    const next = offset + PAGE_SIZE;
    setOffset(next);
    fetchArticles(next, true);
  };

  if (loading) {
    return (
      <div className="space-y-4" aria-live="polite" aria-busy="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-[var(--radius-lg)] border border-[var(--color-negative)]/30 bg-[var(--color-negative)]/10 p-4 text-sm text-[var(--color-negative)]"
      >
        {error}
        <button
          onClick={() => fetchArticles(0, false)}
          className="ml-3 font-medium underline hover:no-underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
        >
          Retry
        </button>
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-8 text-center text-sm text-[var(--color-text-muted)]">
        No news articles found.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {articles.map((article) => (
        <a
          key={article.article_id}
          href={article.url ?? "#"}
          target="_blank"
          rel="noopener noreferrer"
          className="group block rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4 transition-colors hover:border-[var(--color-accent)]/40"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)] transition-colors group-hover:text-[var(--color-accent)]">
              {article.title}
            </h3>
            <ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="inline-flex rounded bg-[var(--color-accent)]/15 px-2 py-0.5 text-xs font-medium text-[var(--color-accent)]">
              {article.source}
            </span>
            <span className="text-xs text-[var(--color-text-muted)]">
              {formatDistanceToNow(new Date(article.publication_date), {
                addSuffix: true,
              })}
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

          {article.content && (
            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-[var(--color-text-muted)]">
              {article.content}
            </p>
          )}
        </a>
      ))}

      {hasMore && (
        <button
          onClick={handleLoadMore}
          disabled={loadingMore}
          className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] py-3 text-sm font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-tertiary)]/40 hover:text-[var(--color-text-primary)] disabled:opacity-50"
        >
          {loadingMore ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading…
            </>
          ) : (
            `Load more (showing ${articles.length})`
          )}
        </button>
      )}
    </div>
  );
}
