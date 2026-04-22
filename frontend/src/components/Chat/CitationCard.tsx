import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

interface Citation {
  title: string;
  source: string;
  url?: string;
  sentiment?: {
    label: "positive" | "negative" | "neutral";
    score?: number;
  };
}

interface CitationCardProps {
  citation: Citation;
  index?: number;
}

export default function CitationCard({ citation, index }: CitationCardProps) {
  const Wrapper = citation.url ? "a" : "div";
  const linkProps = citation.url
    ? {
        href: citation.url,
        target: "_blank" as const,
        rel: "noopener noreferrer",
      }
    : {};

  return (
    <Wrapper
      {...linkProps}
      className={cn(
        "flex items-start gap-2.5 rounded-md border border-border bg-background px-3 py-2 text-left transition-colors",
        citation.url && "hover:border-primary/40 hover:bg-accent/50",
      )}
    >
      {index != null && (
        <span
          className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-muted text-[10px] font-semibold text-muted-foreground"
          aria-hidden="true"
        >
          {index}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-foreground">
          {citation.title}
        </p>
        <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
          {citation.source}
        </p>
      </div>
      {citation.url && (
        <ExternalLink
          className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
      )}
    </Wrapper>
  );
}

export type { Citation };
