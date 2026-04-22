import { useEffect, useRef, useState } from "react";
import { Loader2, CheckCircle2, XCircle, Activity } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { getFinetuningJob } from "@/api/client";
import type { FinetuningJob } from "@/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface TrainingProgressProps {
  jobId: string;
  onComplete?: () => void;
}

interface MetricPoint {
  step: number;
  loss?: number;
  accuracy?: number;
}

function asNumber(v: unknown): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  return undefined;
}

function pickProgress(j: FinetuningJob): number {
  const p = asNumber(j.metrics?.progress);
  if (p != null) return Math.max(0, Math.min(100, p));
  if (j.status === "completed") return 100;
  if (j.status === "running" || j.status === "pending") return 25;
  return 0;
}

export default function TrainingProgress({
  jobId,
  onComplete,
}: TrainingProgressProps) {
  const [job, setJob] = useState<FinetuningJob | null>(null);
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    const poll = async () => {
      try {
        const j = await getFinetuningJob(jobId);
        setJob(j);

        const loss = asNumber(j.metrics?.loss);
        const accuracy = asNumber(j.metrics?.accuracy);
        if (loss != null || accuracy != null) {
          setMetrics((prev) => [
            ...prev,
            { step: prev.length + 1, loss, accuracy },
          ]);
        }

        if (
          j.status === "completed" ||
          j.status === "failed" ||
          j.status === "cancelled"
        ) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          onComplete?.();
        }
      } catch {
        /* ignore polling errors */
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [jobId, onComplete]);

  if (!job) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-10">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const isRunning = job.status === "running" || job.status === "pending";
  const isFailed = job.status === "failed";
  const isDone = job.status === "completed";
  const progress = pickProgress(job);

  const loss = asNumber(job.metrics?.loss);
  const accuracy = asNumber(job.metrics?.accuracy);
  const f1 = asNumber(job.metrics?.f1_score ?? job.metrics?.f1);
  const errorMessage =
    typeof job.metrics?.error === "string"
      ? (job.metrics.error as string)
      : null;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Activity className="h-4 w-4 text-primary" />
          Training job #{job.id}
        </CardTitle>
        <Badge
          variant="outline"
          className={cn(
            "gap-1",
            isFailed && "border-negative/40 text-negative",
            isDone && "border-positive/40 text-positive",
            isRunning && "border-primary/40 text-primary",
          )}
        >
          {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
          {isDone && <CheckCircle2 className="h-3 w-3" />}
          {isFailed && <XCircle className="h-3 w-3" />}
          <span className="capitalize">{job.status}</span>
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-1 flex justify-between text-xs text-muted-foreground">
            <span>{job.dataset_name}</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress
            value={progress}
            className={cn(isFailed && "[&>div]:bg-negative")}
          />
        </div>

        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="rounded-md bg-muted px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Loss
            </p>
            <p className="text-sm font-semibold text-foreground">
              {loss != null ? loss.toFixed(4) : "—"}
            </p>
          </div>
          <div className="rounded-md bg-muted px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Accuracy
            </p>
            <p className="text-sm font-semibold text-foreground">
              {accuracy != null ? `${(accuracy * 100).toFixed(1)}%` : "—"}
            </p>
          </div>
          <div className="rounded-md bg-muted px-3 py-2">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
              F1
            </p>
            <p className="text-sm font-semibold text-foreground">
              {f1 != null ? f1.toFixed(3) : "—"}
            </p>
          </div>
        </div>

        {metrics.length > 1 && (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                />
                <XAxis
                  dataKey="step"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  stroke="hsl(var(--border))"
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  stroke="hsl(var(--border))"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "0.5rem",
                    fontSize: "0.75rem",
                    color: "hsl(var(--popover-foreground))",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "0.75rem" }} />
                <Line
                  type="monotone"
                  dataKey="loss"
                  stroke="hsl(var(--negative))"
                  strokeWidth={2}
                  dot={false}
                  name="Loss"
                />
                <Line
                  type="monotone"
                  dataKey="accuracy"
                  stroke="hsl(var(--positive))"
                  strokeWidth={2}
                  dot={false}
                  name="Accuracy"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {errorMessage && (
          <p className="rounded-md border border-negative/40 bg-negative/10 px-3 py-2 text-xs text-negative">
            {errorMessage}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
