import { useRef, useEffect } from "react";
import { Sparkles } from "lucide-react";
import MessageBubble from "./MessageBubble";
import type { Citation } from "./CitationCard";

interface DisplayMessage {
  id: string | number;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

interface ChatWindowProps {
  messages: DisplayMessage[];
  onSuggestionClick?: (text: string) => void;
}

const SUGGESTIONS = [
  "What's the current sentiment on AAPL?",
  "Which stocks have the most positive buzz on X?",
  "How does news sentiment correlate with price movement?",
];

export default function ChatWindow({
  messages,
  onSuggestionClick,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--color-accent)]/10">
            <Sparkles className="h-6 w-6 text-[var(--color-accent)]" />
          </div>
          <h2 className="text-base font-semibold text-[var(--color-text-primary)]">
            Financial Sentiment Assistant
          </h2>
          <p className="max-w-md text-[13px] text-[var(--color-text-muted)]">
            Ask questions about market sentiment, social buzz, or news analysis.
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => onSuggestionClick?.(q)}
              className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-3.5 py-2 text-[12px] text-[var(--color-text-secondary)] transition-all hover:border-[var(--color-accent)]/30 hover:text-[var(--color-accent)]"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-3xl space-y-5">
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            content={m.content}
            citations={m.citations}
            isStreaming={m.isStreaming}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export type { DisplayMessage };
