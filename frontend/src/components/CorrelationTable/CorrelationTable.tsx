import { useMemo } from "react";
import { useApi } from "@/hooks/useApi";
import { getCorrelations } from "@/api/client";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import type { CorrelationData } from "@/types";

interface CorrelationTableProps {
  ticker: string;
}

function colorForValue(v: number): string {
  if (v > 0.3) return "text-[var(--color-positive)]";
  if (v < -0.3) return "text-[var(--color-negative)]";
  return "text-[var(--color-text-secondary)]";
}

function humanizeType(type: string, timeLag: number | null | undefined): string {
  switch (type) {
    case "pearson":
      return "Pearson (linear)";
    case "spearman":
      return "Spearman (rank)";
    case "rolling_7d":
      return "Rolling 7-day Pearson";
    case "time_lagged":
      return timeLag ? `Time-lagged (lag ${timeLag}d)` : "Time-lagged";
    default:
      return type;
  }
}

function pickLatestPerType(rows: CorrelationData[]): CorrelationData[] {
  // Backend returns newest first; keep only one row per (type, time_lag).
  const seen = new Set<string>();
  const out: CorrelationData[] = [];
  for (const r of rows) {
    const key = `${r.correlation_type}:${r.time_lag ?? "none"}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(r);
  }
  return out;
}

export default function CorrelationTable({ ticker }: CorrelationTableProps) {
  const { data, loading, error, refetch } = useApi(
    () => getCorrelations(ticker),
    [ticker],
  );

  const rows = useMemo(() => (data ? pickLatestPerType(data) : []), [data]);

  if (loading) return <LoadingSpinner message="Loading correlations…" />;
  if (error) return <ErrorMessage message={error} onRetry={refetch} />;

  if (rows.length === 0) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6 text-center text-[12px] text-[var(--color-text-muted)]">
        No correlation data for {ticker.toUpperCase()} yet.
      </div>
    );
  }

  const latestDate = rows[0]?.calculated_date
    ? new Date(rows[0].calculated_date).toLocaleDateString()
    : "—";

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
      <div className="border-b border-[var(--color-border)] px-4 py-3">
        <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
          Sentiment–Price Correlation — {ticker.toUpperCase()}
        </h3>
        <p className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
          Most recent calculation: {latestDate}
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-[10px] uppercase tracking-wider text-[var(--color-text-muted)]">
              <th className="px-4 py-2 font-semibold">Metric</th>
              <th className="px-4 py-2 text-right font-semibold">Value</th>
              <th className="px-4 py-2 text-right font-semibold">p-value</th>
              <th className="hidden px-4 py-2 text-right font-semibold sm:table-cell">
                Samples
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.correlation_type}-${row.time_lag ?? "none"}-${row.correlation_id}`}
                className="border-b border-[var(--color-border-subtle)] last:border-0 transition-colors hover:bg-[var(--color-bg-tertiary)]/30"
              >
                <td className="px-4 py-2.5 font-medium text-[var(--color-text-primary)]">
                  {humanizeType(row.correlation_type, row.time_lag)}
                </td>
                <td
                  className={`px-4 py-2.5 text-right font-mono ${colorForValue(row.correlation_value)}`}
                >
                  {row.correlation_value > 0 ? "+" : ""}
                  {row.correlation_value.toFixed(4)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-[var(--color-text-muted)]">
                  {row.p_value != null ? row.p_value.toExponential(2) : "—"}
                </td>
                <td className="hidden px-4 py-2.5 text-right font-mono text-[var(--color-text-muted)] sm:table-cell">
                  {row.sample_size ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
