import ReactMarkdown from "react-markdown";
import { User, Bot } from "lucide-react";
import CitationCard from "./CitationCard";
import type { Citation } from "./CitationCard";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

export default function MessageBubble({
  role,
  content,
  citations,
  isStreaming,
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
          isUser
            ? "bg-[var(--color-accent)]/20"
            : "bg-[var(--color-bg-tertiary)]"
        }`}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5 text-[var(--color-accent)]" />
        ) : (
          <Bot className="h-3.5 w-3.5 text-[var(--color-text-secondary)]" />
        )}
      </div>

      <div
        className={`max-w-[78%] space-y-2 ${isUser ? "items-end" : "items-start"}`}
      >
        <div
          className={`rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
            isUser
              ? "rounded-br-md bg-[var(--color-accent)] text-white"
              : "rounded-bl-md bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-[var(--color-text-primary)]"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:mb-2 prose-headings:mt-3 prose-pre:bg-[var(--color-bg-primary)] prose-pre:border prose-pre:border-[var(--color-border)]">
              <ReactMarkdown>{content}</ReactMarkdown>
              {isStreaming && (
                <span className="inline-block h-4 w-0.5 animate-pulse bg-[var(--color-accent)] ml-0.5 align-text-bottom" />
              )}
            </div>
          )}
        </div>

        {citations && citations.length > 0 && (
          <div className="flex flex-col gap-1 pl-1">
            {citations.map((c, i) => (
              <CitationCard key={i} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
