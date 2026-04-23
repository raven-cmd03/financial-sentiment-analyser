import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

interface Citation {
  title: string;
  source: string;
  url?: string;
  publicationDate?: string;
  ticker?: string;
  sentiment?: {
    label: "positive" | "negative" | "neutral";
    score?: number;
  };
}

interface CitationCardProps {
  citation: Citation;
  index?: number;
}

const DATE_FORMAT = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
});

function formatPublicationDate(raw?: string): string | null {
  if (!raw) return null;
  // Backend emits "YYYY-MM-DD HH:MM:SS" for historical rows and an empty
  // string when no date is known; guard both.
  const iso = raw.includes("T") ? raw : raw.replace(" ", "T");
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return null;
  return DATE_FORMAT.format(parsed);
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

  const prettyDate = formatPublicationDate(citation.publicationDate);

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
        <p className="mt-0.5 flex items-center gap-1.5 truncate text-[10px] text-muted-foreground">
          <span className="truncate">{citation.source}</span>
          {citation.ticker && (
            <span className="shrink-0 rounded bg-muted px-1 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider text-foreground/80">
              {citation.ticker}
            </span>
          )}
          {prettyDate && (
            <>
              <span className="shrink-0 text-muted-foreground/40" aria-hidden>
                ·
              </span>
              <span className="shrink-0 tabular-nums">{prettyDate}</span>
            </>
          )}
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
