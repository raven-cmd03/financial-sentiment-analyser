import { AlertTriangle } from "lucide-react";

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export default function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-negative)]/20 bg-[var(--color-negative)]/5 px-4 py-3"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-negative)]" />
      <div className="flex-1">
        <p className="text-[13px] font-medium text-[var(--color-negative)]">
          Something went wrong
        </p>
        <p className="mt-0.5 text-[12px] text-[var(--color-text-secondary)]">
          {message}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 text-[12px] font-medium text-[var(--color-accent)] transition-colors hover:text-[var(--color-accent-hover)]"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
