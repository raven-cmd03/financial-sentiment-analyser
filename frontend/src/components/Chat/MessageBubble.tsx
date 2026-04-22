import ReactMarkdown from "react-markdown";
import { User, Sparkles } from "lucide-react";
import CitationCard from "./CitationCard";
import type { Citation } from "./CitationCard";
import { cn } from "@/lib/utils";

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
    <article
      className={cn(
        "group flex gap-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
      aria-label={isUser ? "Your message" : "Assistant message"}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
          isUser
            ? "border-primary/40 bg-primary/10 text-primary"
            : "border-border bg-card text-muted-foreground",
        )}
        aria-hidden="true"
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Sparkles className="h-4 w-4 text-primary" />
        )}
      </div>

      <div
        className={cn(
          "flex min-w-0 max-w-[85%] flex-col gap-2",
          isUser ? "items-end" : "items-start",
        )}
      >
        <div
          className={cn(
            "w-fit max-w-full rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
            isUser
              ? "rounded-br-md bg-primary text-primary-foreground"
              : "rounded-bl-md border border-border bg-card text-card-foreground",
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{content}</p>
          ) : content.length === 0 && isStreaming ? (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/60 [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/60 [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/60" />
              </span>
              Thinking…
            </span>
          ) : (
            <div
              className={cn(
                "prose prose-sm max-w-none dark:prose-invert",
                "prose-p:my-1.5 prose-p:leading-relaxed",
                "prose-headings:mb-2 prose-headings:mt-3 prose-headings:font-semibold",
                "prose-strong:text-foreground",
                "prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:text-xs prose-code:font-medium prose-code:before:content-[''] prose-code:after:content-['']",
                "prose-pre:rounded-md prose-pre:border prose-pre:border-border prose-pre:bg-muted",
                "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5",
              )}
            >
              <ReactMarkdown>{content}</ReactMarkdown>
              {isStreaming && (
                <span
                  aria-hidden="true"
                  className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-primary align-text-bottom"
                />
              )}
            </div>
          )}
        </div>

        {!isUser && citations && citations.length > 0 && (
          <div className="w-full">
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              {citations.length} source{citations.length !== 1 ? "s" : ""}
            </p>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {citations.map((c, i) => (
                <CitationCard key={i} citation={c} index={i + 1} />
              ))}
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
