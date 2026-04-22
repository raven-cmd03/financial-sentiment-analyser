import SentimentBadge from "@/components/common/SentimentBadge";

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
}

export default function CitationCard({ citation }: CitationCardProps) {
  const Wrapper = citation.url ? "a" : "div";
  const linkProps = citation.url
    ? { href: citation.url, target: "_blank" as const, rel: "noopener noreferrer" }
    : {};

  return (
    <Wrapper
      {...linkProps}
      className="flex items-start gap-2 rounded-md border border-gray-700 bg-gray-800/60 px-3 py-2 text-left transition-colors hover:border-gray-600"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-gray-200">
          {citation.title}
        </p>
        <p className="mt-0.5 text-[10px] text-gray-500">{citation.source}</p>
      </div>
      {citation.sentiment && (
        <SentimentBadge
          label={citation.sentiment.label}
          score={citation.sentiment.score}
        />
      )}
    </Wrapper>
  );
}

export type { Citation };
