import { formatDistanceToNow } from "date-fns";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import type { ChatSession } from "@/types";

interface SessionListProps {
  sessions: ChatSession[];
  activeId: string | number | null;
  onSelect: (id: string | number) => void;
  onCreate: () => void;
  onDelete: (id: string | number) => void;
}

export default function SessionList({
  sessions,
  activeId,
  onSelect,
  onCreate,
  onDelete,
}: SessionListProps) {
  return (
    <div className="flex h-full flex-col">
      <button
        onClick={onCreate}
        className="mx-3 mt-3 flex items-center justify-center gap-2 rounded-[var(--radius-md)] border border-dashed border-[var(--color-border)] py-2 text-[12px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent)]/40 hover:text-[var(--color-accent)]"
      >
        <Plus className="h-3.5 w-3.5" />
        New Chat
      </button>

      <div className="mt-2 flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <p className="px-4 py-8 text-center text-[11px] text-[var(--color-text-muted)]">
            No conversations yet
          </p>
        ) : (
          <ul className="space-y-0.5 px-2">
            {sessions.map((s) => (
              <li key={s.id}>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") onSelect(s.id);
                  }}
                  className={`group flex w-full cursor-pointer items-start gap-2 rounded-[var(--radius-md)] px-2.5 py-2 text-left transition-all duration-150 ${
                    activeId === s.id
                      ? "bg-[var(--color-accent)]/10 text-[var(--color-accent-hover)]"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]/40"
                  }`}
                >
                  <MessageSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-40" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] font-medium">
                      {s.title || "Untitled Chat"}
                    </p>
                    <p className="mt-0.5 text-[10px] text-[var(--color-text-muted)]">
                      {formatDistanceToNow(new Date(s.created_at), {
                        addSuffix: true,
                      })}
                      {" · "}
                      {s.message_count} msg{s.message_count !== 1 && "s"}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(s.id);
                    }}
                    className="mt-0.5 opacity-0 transition-opacity group-hover:opacity-100"
                    title="Delete session"
                  >
                    <Trash2 className="h-3 w-3 text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-negative)]" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
