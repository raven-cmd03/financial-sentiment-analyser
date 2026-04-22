import { type ReactNode } from "react";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  sublabel?: string;
  icon: ReactNode;
  tone?: "primary" | "positive" | "negative" | "neutral";
  spark?: number[];
}

const toneClasses: Record<
  NonNullable<KpiCardProps["tone"]>,
  { bg: string; text: string; stroke: string }
> = {
  primary: {
    bg: "bg-primary/10",
    text: "text-primary",
    stroke: "hsl(var(--primary))",
  },
  positive: {
    bg: "bg-positive/10",
    text: "text-positive",
    stroke: "hsl(var(--positive))",
  },
  negative: {
    bg: "bg-negative/10",
    text: "text-negative",
    stroke: "hsl(var(--negative))",
  },
  neutral: {
    bg: "bg-muted",
    text: "text-muted-foreground",
    stroke: "hsl(var(--muted-foreground))",
  },
};

export default function KpiCard({
  label,
  value,
  sublabel,
  icon,
  tone = "primary",
  spark,
}: KpiCardProps) {
  const t = toneClasses[tone];
  const sparkData = (spark ?? []).map((v, i) => ({ i, v }));
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            t.bg,
            t.text,
          )}
          aria-hidden="true"
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p
            className={cn(
              "truncate text-xl font-semibold leading-snug tabular-nums",
              t.text,
            )}
          >
            {value}
          </p>
          {sublabel && (
            <p className="truncate text-[11px] text-muted-foreground">
              {sublabel}
            </p>
          )}
        </div>
        {sparkData.length > 1 && (
          <div className="h-9 w-20 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sparkData}>
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={t.stroke}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
