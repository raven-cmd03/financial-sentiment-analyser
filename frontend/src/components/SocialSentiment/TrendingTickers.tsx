import { useApi } from "@/hooks/useApi";
import { getTrendingTickers } from "@/api/client";
import { TrendingUp, Loader2 } from "lucide-react";

function RankBadge({ rank }: { rank: number }) {
  const colors =
    rank === 1
      ? "bg-yellow-500/20 text-yellow-400"
      : rank === 2
        ? "bg-gray-400/20 text-gray-300"
        : rank === 3
          ? "bg-orange-500/20 text-orange-400"
          : "bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)]";

  return (
    <span
      className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${colors}`}
    >
      {rank}
    </span>
  );
}

export default function TrendingTickers() {
  const { data, loading, error } = useApi(() => getTrendingTickers(), []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="text-center text-sm text-[var(--color-negative)] py-4">
        {error}
      </div>
    );
  }

  const tickers = (data ?? []).slice(0, 10);

  if (tickers.length === 0) {
    return (
      <div className="text-center text-sm text-[var(--color-text-muted)] py-4">
        No trending tickers
      </div>
    );
  }

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
      <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-3">
        <TrendingUp className="h-4 w-4 text-[var(--color-accent)]" />
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
          Trending on X
        </h3>
      </div>
      <ul className="divide-y divide-[var(--color-border-subtle)]">
        {tickers.map((t, i) => (
          <li
            key={t.ticker_symbol}
            className="flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--color-bg-tertiary)]/30 transition-colors"
          >
            <RankBadge rank={i + 1} />
            <span className="flex-1 text-sm font-medium text-[var(--color-text-primary)]">
              ${t.ticker_symbol}
            </span>
            <span className="text-xs text-[var(--color-text-muted)]">
              Buzz {Number(t.buzz_score ?? 0).toFixed(0)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
