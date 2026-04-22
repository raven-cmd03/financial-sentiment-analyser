import { useMemo } from "react";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { ChatSession } from "@/types";

interface SessionListProps {
  sessions: ChatSession[];
  activeId: string | number | null;
  onSelect: (id: string | number) => void;
  onCreate: () => void;
  onDelete: (id: string | number) => void;
}

type BucketKey = "today" | "yesterday" | "week" | "month" | "older";

const BUCKET_LABEL: Record<BucketKey, string> = {
  today: "Today",
  yesterday: "Yesterday",
  week: "Previous 7 days",
  month: "Previous 30 days",
  older: "Older",
};

const BUCKET_ORDER: BucketKey[] = [
  "today",
  "yesterday",
  "week",
  "month",
  "older",
];

function bucketFor(value?: string | null): BucketKey {
  if (!value) return "today";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "today";

  const now = new Date();
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  ).getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  const t = d.getTime();

  if (t >= startOfToday) return "today";
  if (t >= startOfToday - dayMs) return "yesterday";
  if (t >= startOfToday - 7 * dayMs) return "week";
  if (t >= startOfToday - 30 * dayMs) return "month";
  return "older";
}

export default function SessionList({
  sessions,
  activeId,
  onSelect,
  onCreate,
  onDelete,
}: SessionListProps) {
  const grouped = useMemo(() => {
    const buckets: Record<BucketKey, ChatSession[]> = {
      today: [],
      yesterday: [],
      week: [],
      month: [],
      older: [],
    };
    const sorted = [...sessions].sort((a, b) => {
      const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
      const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
      return tb - ta;
    });
    for (const s of sorted) {
      buckets[bucketFor(s.created_at)].push(s);
    }
    return buckets;
  }, [sessions]);

  return (
    <div className="flex h-full flex-col">
      <div className="px-3 pb-3 pt-3">
        <Button
          onClick={onCreate}
          size="sm"
          className="w-full justify-center gap-2"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden="true" />
          New chat
        </Button>
      </div>

      <ScrollArea className="flex-1">
        {sessions.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-12 text-center">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-full bg-muted"
              aria-hidden="true"
            >
              <MessageSquarePlus className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="text-xs font-medium text-foreground">
              No conversations yet
            </p>
            <p className="max-w-[180px] text-[11px] leading-relaxed text-muted-foreground">
              Start a new chat to ask about tickers, news, or sentiment.
            </p>
          </div>
        ) : (
          <div className="pb-4">
            {BUCKET_ORDER.map((key) => {
              const items = grouped[key];
              if (items.length === 0) return null;
              return (
                <section
                  key={key}
                  aria-label={BUCKET_LABEL[key]}
                  className="mt-3 first:mt-1"
                >
                  <h3 className="px-4 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80">
                    {BUCKET_LABEL[key]}
                  </h3>
                  <ul className="space-y-0.5 px-2">
                    {items.map((s) => (
                      <SessionRow
                        key={s.id}
                        session={s}
                        active={activeId === s.id}
                        onSelect={onSelect}
                        onDelete={onDelete}
                      />
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

interface SessionRowProps {
  session: ChatSession;
  active: boolean;
  onSelect: (id: string | number) => void;
  onDelete: (id: string | number) => void;
}

function SessionRow({ session, active, onSelect, onDelete }: SessionRowProps) {
  const title = session.title?.trim() || "Untitled chat";

  return (
    <li>
      <div
        role="button"
        tabIndex={0}
        aria-current={active ? "true" : undefined}
        onClick={() => onSelect(session.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(session.id);
          }
        }}
        className={cn(
          "group relative flex w-full cursor-pointer items-center gap-2 rounded-md pl-3 pr-1.5 py-2 text-left transition-colors",
          active
            ? "bg-primary/10 text-primary"
            : "text-foreground hover:bg-accent",
        )}
      >
        {active && (
          <span
            className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary"
            aria-hidden="true"
          />
        )}
        <p
          className={cn(
            "min-w-0 flex-1 truncate text-xs",
            active ? "font-medium" : "font-normal",
          )}
          title={title}
        >
          {title}
        </p>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(session.id);
          }}
          className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded text-muted-foreground transition-all",
            "opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
            "hover:bg-negative/10 hover:text-negative",
          )}
          aria-label={`Delete chat ${title}`}
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    </li>
  );
}
