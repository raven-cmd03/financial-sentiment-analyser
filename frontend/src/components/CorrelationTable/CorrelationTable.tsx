import { useMemo } from "react";
import { Activity } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { getCorrelations } from "@/api/client";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ErrorMessage from "@/components/common/ErrorMessage";
import EmptyState from "@/components/common/EmptyState";
import {
  Card,
  CardContent,
  CardDescription,
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
import { cn } from "@/lib/utils";
import type { CorrelationData } from "@/types";

interface CorrelationTableProps {
  ticker: string;
}

function colorForValue(v: number): string {
  if (v > 0.3) return "text-positive";
  if (v < -0.3) return "text-negative";
  return "text-muted-foreground";
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
      <Card>
        <CardContent className="p-6">
          <EmptyState
            icon={Activity}
            title="No correlation data yet"
            description={`Correlation jobs run nightly. Come back after the next run for ${ticker.toUpperCase()}.`}
          />
        </CardContent>
      </Card>
    );
  }

  const latestDate = rows[0]?.calculated_date
    ? new Date(rows[0].calculated_date).toLocaleDateString()
    : "—";

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Sentiment–Price Correlation — {ticker.toUpperCase()}
        </CardTitle>
        <CardDescription>
          Most recent calculation: {latestDate}
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metric</TableHead>
              <TableHead className="text-right">Value</TableHead>
              <TableHead className="text-right">p-value</TableHead>
              <TableHead className="hidden text-right sm:table-cell">
                Samples
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow
                key={`${row.correlation_type}-${row.time_lag ?? "none"}-${row.correlation_id}`}
              >
                <TableCell className="font-medium">
                  {humanizeType(row.correlation_type, row.time_lag)}
                </TableCell>
                <TableCell
                  className={cn(
                    "text-right font-mono",
                    colorForValue(row.correlation_value),
                  )}
                >
                  {row.correlation_value > 0 ? "+" : ""}
                  {row.correlation_value.toFixed(4)}
                </TableCell>
                <TableCell className="text-right font-mono text-muted-foreground">
                  {row.p_value != null ? row.p_value.toExponential(2) : "—"}
                </TableCell>
                <TableCell className="hidden text-right font-mono text-muted-foreground sm:table-cell">
                  {row.sample_size ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
