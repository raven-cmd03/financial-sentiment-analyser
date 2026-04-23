import { useMemo } from "react";
import { Activity, Info } from "lucide-react";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
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

type MetricExplanation = {
  subtitle: string;
  detail: string;
};

function explainType(
  type: string,
  timeLag: number | null | undefined,
): MetricExplanation {
  switch (type) {
    case "pearson":
      return {
        subtitle: "Same-day linear association",
        detail:
          "Standard Pearson r between each day's aggregate sentiment score and that day's price return. Captures only straight-line relationships; ranges −1 to +1 with 0 meaning no linear link.",
      };
    case "spearman":
      return {
        subtitle: "Same-day rank association",
        detail:
          "Spearman ρ ranks both series before correlating, so it catches any monotonic relationship (including non-linear ones) and is far less sensitive to outliers and skew than Pearson.",
      };
    case "rolling_7d":
      return {
        subtitle: "Most recent 7-day window",
        detail:
          "Pearson r computed over just the trailing 7 trading days. Useful for spotting short-term regime shifts — use alongside the full-sample Pearson, which is more statistically stable.",
      };
    case "time_lagged":
      return {
        subtitle: timeLag
          ? `Sentiment leads price by ${timeLag} day${timeLag === 1 ? "" : "s"}`
          : "Sentiment leads price",
        detail: timeLag
          ? `Pearson r between today's sentiment and the price return ${timeLag} trading day${timeLag === 1 ? "" : "s"} later. Positive values suggest sentiment has some predictive signal; remember that a high p-value (> 0.05) means the lead effect is not statistically distinguishable from noise.`
          : "Pearson r between sentiment and a future price return, testing whether sentiment has predictive lead on price.",
      };
    default:
      return { subtitle: "", detail: "" };
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
            {rows.map((row) => {
              const explanation = explainType(
                row.correlation_type,
                row.time_lag,
              );
              return (
              <TableRow
                key={`${row.correlation_type}-${row.time_lag ?? "none"}-${row.correlation_id}`}
              >
                <TableCell className="font-medium align-top">
                  <div className="flex items-start gap-1.5">
                    <div className="flex flex-col">
                      <span>
                        {humanizeType(row.correlation_type, row.time_lag)}
                      </span>
                      {explanation.subtitle && (
                        <span className="text-xs font-normal text-muted-foreground">
                          {explanation.subtitle}
                        </span>
                      )}
                    </div>
                    {explanation.detail && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            aria-label={`About ${humanizeType(row.correlation_type, row.time_lag)}`}
                            className="mt-0.5 text-muted-foreground transition-colors hover:text-foreground focus-visible:text-foreground focus-visible:outline-none"
                          >
                            <Info className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent
                          side="top"
                          align="start"
                          className="max-w-xs text-xs leading-relaxed"
                        >
                          {explanation.detail}
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </div>
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
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
