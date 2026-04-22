import { Loader2 } from "lucide-react";

interface LoadingSpinnerProps {
  size?: number;
  message?: string;
}

export default function LoadingSpinner({
  size = 24,
  message = "Loading…",
}: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="flex flex-col items-center justify-center gap-2.5 py-14"
    >
      <Loader2
        className="animate-spin text-[var(--color-accent)]"
        size={size}
        aria-hidden="true"
      />
      {message && (
        <p className="text-[12px] text-[var(--color-text-muted)]">{message}</p>
      )}
      <span className="sr-only">{message || "Loading"}</span>
    </div>
  );
}
