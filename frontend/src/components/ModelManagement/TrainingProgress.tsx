import { useEffect, useState, useRef } from "react";
import { Loader2, CheckCircle, XCircle } from "lucide-react";
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

interface TrainingProgressProps {
  jobId: string;
  onComplete?: () => void;
}

interface MetricPoint {
  step: number;
  loss?: number;
  accuracy?: number;
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

        if (j.metrics) {
          setMetrics((prev) => [
            ...prev,
            {
              step: prev.length + 1,
              loss: j.metrics?.loss,
              accuracy: j.metrics?.accuracy,
            },
          ]);
        }

        if (j.status === "completed" || j.status === "failed" || j.status === "cancelled") {
          clearInterval(intervalRef.current);
          onComplete?.();
        }
      } catch {
        /* ignore polling errors */
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 3000);
    return () => clearInterval(intervalRef.current);
  }, [jobId, onComplete]);

  if (!job) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-gray-500" />
      </div>
    );
  }

  const isRunning = job.status === "running" || job.status === "pending";
  const isFailed = job.status === "failed";
  const isDone = job.status === "completed";

  return (
    <div className="space-y-4 rounded-lg border border-gray-700 bg-gray-800 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRunning && <Loader2 className="h-4 w-4 animate-spin text-blue-400" />}
          {isDone && <CheckCircle className="h-4 w-4 text-emerald-400" />}
          {isFailed && <XCircle className="h-4 w-4 text-red-400" />}
          <span className="text-sm font-medium text-gray-200 capitalize">
            {job.status}
          </span>
        </div>
        <span className="text-xs text-gray-500">{job.model_name}</span>
      </div>

      {/* Progress bar */}
      <div>
        <div className="mb-1 flex justify-between text-xs text-gray-400">
          <span>Progress</span>
          <span>{Math.round(job.progress)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-700">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isFailed ? "bg-red-500" : isDone ? "bg-emerald-500" : "bg-blue-500"
            }`}
            style={{ width: `${job.progress}%` }}
          />
        </div>
      </div>

      {/* Live metrics */}
      {job.metrics && (
        <div className="grid grid-cols-3 gap-3 text-center">
          {job.metrics.loss !== undefined && (
            <div className="rounded-md bg-gray-900 px-3 py-2">
              <p className="text-[10px] text-gray-500">Loss</p>
              <p className="text-sm font-semibold text-gray-200">
                {job.metrics.loss.toFixed(4)}
              </p>
            </div>
          )}
          {job.metrics.accuracy !== undefined && (
            <div className="rounded-md bg-gray-900 px-3 py-2">
              <p className="text-[10px] text-gray-500">Accuracy</p>
              <p className="text-sm font-semibold text-gray-200">
                {(job.metrics.accuracy * 100).toFixed(1)}%
              </p>
            </div>
          )}
          {job.metrics.f1_score !== undefined && (
            <div className="rounded-md bg-gray-900 px-3 py-2">
              <p className="text-[10px] text-gray-500">F1 Score</p>
              <p className="text-sm font-semibold text-gray-200">
                {job.metrics.f1_score.toFixed(3)}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Chart */}
      {metrics.length > 1 && (
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={metrics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="step"
                tick={{ fontSize: 10, fill: "#9ca3af" }}
                stroke="#4b5563"
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#9ca3af" }}
                stroke="#4b5563"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  borderRadius: "0.5rem",
                  fontSize: "0.75rem",
                  color: "#d1d5db",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "0.75rem" }} />
              <Line
                type="monotone"
                dataKey="loss"
                stroke="#ef4444"
                strokeWidth={2}
                dot={false}
                name="Loss"
              />
              <Line
                type="monotone"
                dataKey="accuracy"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
                name="Accuracy"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Error message */}
      {job.error_message && (
        <p className="text-xs text-red-400">{job.error_message}</p>
      )}
    </div>
  );
}
