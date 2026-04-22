import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  size?: number;
  message?: string;
  className?: string;
}

export default function LoadingSpinner({
  size = 22,
  message = "Loading…",
  className,
}: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cn(
        "flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground",
        className,
      )}
    >
      <Loader2
        className="animate-spin text-primary"
        size={size}
        aria-hidden="true"
      />
      {message && <p className="text-xs">{message}</p>}
      <span className="sr-only">{message || "Loading"}</span>
    </div>
  );
}
