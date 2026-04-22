import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const SPARSE_DATA_THRESHOLD = 6;

/**
 * Recharts' auto x-axis spacing looks terrible with 1-5 points (it either
 * duplicates or hides ticks). Hand-pick evenly spaced indices instead and
 * let Recharts render them as explicit `ticks`.
 */
export function pickXAxisTicks<T>(data: T[], key: keyof T, desired = 6): string[] {
  if (data.length === 0) return [];
  if (data.length <= desired) {
    return data.map((d) => String(d[key]));
  }
  const step = (data.length - 1) / (desired - 1);
  const out: string[] = [];
  for (let i = 0; i < desired; i += 1) {
    const idx = Math.round(i * step);
    out.push(String(data[idx][key]));
  }
  return out;
}

interface ChartCardProps {
  title: string;
  subtitle?: string;
  badge?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * Reusable card shell so every chart on the site has identical padding,
 * typography and border treatment. Avoids drifting one-offs.
 */
export function ChartCard({
  title,
  subtitle,
  badge,
  action,
  children,
  className,
}: ChartCardProps) {
  return (
    <section
      className={cn(
        "rounded-lg border border-border bg-card p-5 shadow-sm",
        className,
      )}
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          {subtitle && (
            <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {action}
          {badge && (
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              {badge}
            </span>
          )}
        </div>
      </div>
      {children}
    </section>
  );
}

interface ChartTooltipRow {
  label: string;
  value: string;
  color?: string;
  accent?: "positive" | "negative" | "neutral";
}

interface ChartTooltipProps {
  title: string;
  rows: ChartTooltipRow[];
}

/** Shared tooltip body — used via recharts' `content={<ChartTooltip ... />}`. */
export function ChartTooltip({ title, rows }: ChartTooltipProps) {
  return (
    <div className="rounded-md border border-border bg-popover p-3 text-xs text-popover-foreground shadow-lg">
      <p className="mb-1.5 font-semibold">{title}</p>
      <div className="space-y-0.5">
        {rows.map((r) => (
          <div
            key={r.label}
            className="flex items-center justify-between gap-6"
          >
            <span className="flex items-center gap-1.5 text-muted-foreground">
              {r.color && (
                <span
                  aria-hidden="true"
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: r.color }}
                />
              )}
              {r.label}
            </span>
            <span
              className={cn(
                "font-mono",
                r.accent === "positive" && "text-positive",
                r.accent === "negative" && "text-negative",
                !r.accent && "text-foreground",
              )}
            >
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
