import { useRef, useEffect } from "react";
import { Sparkles, TrendingUp, BarChart3, Search, Info } from "lucide-react";
import MessageBubble from "./MessageBubble";
import type { Citation } from "./CitationCard";
import { Button } from "@/components/ui/button";

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

const SUGGESTIONS: Array<{
  icon: typeof Sparkles;
  text: string;
}> = [
  { icon: Search, text: "What's the current sentiment on AAPL?" },
  { icon: TrendingUp, text: "Which stocks have the most positive buzz on X?" },
  {
    icon: BarChart3,
    text: "How does news sentiment correlate with price movement?",
  },
  { icon: Info, text: "Summarise yesterday's top negative news across tech." },
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
      <div className="flex flex-1 items-center justify-center overflow-y-auto px-4 py-10">
        <div className="flex w-full max-w-2xl flex-col items-center gap-8 text-center">
          <div className="flex flex-col items-center gap-4">
            <div
              className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-1 ring-primary/20"
              aria-hidden="true"
            >
              <Sparkles className="h-6 w-6" />
            </div>
            <div className="space-y-1.5">
              <h2 className="text-2xl font-semibold tracking-tight">
                Financial sentiment assistant
              </h2>
              <p className="mx-auto max-w-md text-sm text-muted-foreground">
                Grounded in every article and social post we've collected. Ask
                about tickers, sectors, or correlations — responses cite their
                sources.
              </p>
            </div>
          </div>

          <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
            {SUGGESTIONS.map(({ icon: Icon, text }) => (
              <Button
                key={text}
                variant="outline"
                className="group h-auto items-start justify-start gap-3 whitespace-normal px-4 py-3 text-left"
                onClick={() => onSuggestionClick?.(text)}
              >
                <Icon
                  className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
                  aria-hidden="true"
                />
                <span className="text-sm font-normal text-foreground">
                  {text}
                </span>
              </Button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
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
