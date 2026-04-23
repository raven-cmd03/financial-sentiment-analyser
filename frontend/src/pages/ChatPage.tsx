import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { MessageSquare, AlertTriangle, Sparkles } from "lucide-react";
import { toast } from "sonner";
import {
  createChatSession,
  getChatSessions,
  getChatSession,
  sendChatMessageUrl,
  deleteChatSession,
  getApiKey,
  getBackendStatus,
  isLockedError,
} from "@/api/client";
import SessionList from "@/components/Chat/SessionList";
import ChatWindow from "@/components/Chat/ChatWindow";
import ChatInput from "@/components/Chat/ChatInput";
import type { DisplayMessage } from "@/components/Chat/ChatWindow";
import type { ChatSession } from "@/types";
import type { Citation } from "@/components/Chat/CitationCard";
import LockedStateCard from "@/components/common/LockedStateCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

function prettifyModelName(raw: string | null): string {
  if (!raw) return "Groq";
  // "llama-3.3-70b-versatile" → "Llama-3.3 70B"
  const match = raw.match(/^llama-(\d+(?:\.\d+)?)-(\d+)b/i);
  if (match) return `Llama-${match[1]} ${match[2]}B`;
  return raw;
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | number | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [locked, setLocked] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [modelName, setModelName] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Fire-and-forget; badge falls back to a generic label if this fails,
    // so we don't surface the error to the user.
    getBackendStatus()
      .then((s) => setModelName(s.groq_model))
      .catch(() => setModelName(null));
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const data = await getChatSessions();
      setSessions(data);
      setLocked(false);
      setLoadError(null);
    } catch (err) {
      if (isLockedError(err)) {
        setLocked(true);
      } else {
        setLoadError((err as Error).message);
      }
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const selectSession = useCallback(async (id: string | number) => {
    setActiveId(id);
    try {
      const { messages: msgs } = await getChatSession(String(id));
      setMessages(
        msgs.map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          citations: normalizeCitations(m.citations),
        })),
      );
    } catch {
      setMessages([]);
    }
  }, []);

  const handleCreate = useCallback(async () => {
    try {
      const session = await createChatSession();
      setSessions((prev) => [session, ...prev]);
      setActiveId(session.id);
      setMessages([]);
    } catch (err) {
      if (isLockedError(err)) setLocked(true);
      console.error("Failed to create session:", err);
    }
  }, []);

  const handleDelete = useCallback(
    async (id: string | number) => {
      try {
        await deleteChatSession(String(id));
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeId === id) {
          setActiveId(null);
          setMessages([]);
        }
      } catch (err) {
        console.error("Failed to delete session:", err);
      }
    },
    [activeId],
  );

  const handleSend = useCallback(
    async (content: string) => {
      let sessionId = activeId;

      if (!sessionId) {
        try {
          const session = await createChatSession(content.slice(0, 50));
          setSessions((prev) => [session, ...prev]);
          sessionId = session.id;
          setActiveId(sessionId);
        } catch (err) {
          if (isLockedError(err)) setLocked(true);
          return;
        }
      }

      const userMsg: DisplayMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
      };
      const assistantMsg: DisplayMessage = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setStreaming(true);

      try {
        const url = sendChatMessageUrl(sessionId);
        const controller = new AbortController();
        abortRef.current = controller;

        const apiKey = getApiKey();
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(apiKey ? { "X-API-Key": apiKey } : {}),
          },
          body: JSON.stringify({ content }),
          signal: controller.signal,
        });

        if (response.status === 401 || response.status === 403) {
          setLocked(true);
          throw new Error("API key required");
        }

        if (response.status === 503) {
          toast.error("Chat is temporarily unavailable", {
            description:
              "The Groq / LLM backend returned 503. Check provider status and try again.",
          });
          throw new Error("Service unavailable");
        }

        if (!response.ok || !response.body) {
          throw new Error("Stream failed");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let fullContent = "";
        let citations: Citation[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const payload = line.slice(6);
              if (payload.trim() === "[DONE]") continue;

              try {
                const parsed = JSON.parse(payload) as {
                  token?: string;
                  citations?: Citation[];
                };
                if (parsed.token) {
                  fullContent += parsed.token;
                }
                if (parsed.citations) {
                  citations = parsed.citations;
                }
              } catch {
                fullContent += payload;
              }
            }
          }

          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, content: fullContent, citations, isStreaming: true }
                : m,
            ),
          );
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, content: fullContent, citations, isStreaming: false }
              : m,
          ),
        );

        loadSessions();
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    content:
                      "Sorry, an error occurred while streaming the response. Please try again.",
                    isStreaming: false,
                  }
                : m,
            ),
          );
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [activeId, loadSessions],
  );

  const handleSuggestion = useCallback(
    (text: string) => {
      handleSend(text);
    },
    [handleSend],
  );

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeId) ?? null,
    [sessions, activeId],
  );

  if (locked) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-10">
        <LockedStateCard
          title="Chat is locked"
          description="The chat endpoints require the backend API_KEY. Set API_KEY on the backend service and VITE_API_KEY on the frontend, then reload."
          onRetry={() => {
            setLocked(false);
            loadSessions();
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col bg-background">
      {loadError && (
        <div className="border-b border-border bg-background px-4 py-2">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Couldn't load chat sessions</AlertTitle>
            <AlertDescription>{loadError}</AlertDescription>
          </Alert>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <aside
          aria-label="Chat sessions"
          className="hidden w-[260px] shrink-0 flex-col border-r border-border bg-card md:flex"
        >
          <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
            <MessageSquare
              className="h-4 w-4 text-primary"
              aria-hidden="true"
            />
            <h2 className="text-sm font-semibold text-foreground">Chats</h2>
            {sessions.length > 0 && (
              <span className="ml-auto rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                {sessions.length}
              </span>
            )}
          </div>
          <SessionList
            sessions={sessions}
            activeId={activeId}
            onSelect={selectSession}
            onCreate={handleCreate}
            onDelete={handleDelete}
          />
        </aside>

        <section
          aria-label="Conversation"
          className="flex min-w-0 flex-1 flex-col"
        >
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background/80 px-5 backdrop-blur">
            <div className="flex min-w-0 items-center gap-2.5">
              <Sparkles
                className="h-4 w-4 shrink-0 text-primary"
                aria-hidden="true"
              />
              <h1 className="truncate text-sm font-semibold text-foreground">
                {activeSession?.title || "New conversation"}
              </h1>
            </div>
            <Badge
              variant="outline"
              className="hidden gap-1.5 font-mono text-[10px] text-muted-foreground sm:inline-flex"
              title={modelName ?? undefined}
            >
              <span
                className="h-1.5 w-1.5 rounded-full bg-positive"
                aria-hidden="true"
              />
              {`Groq · ${prettifyModelName(modelName)}`}
            </Badge>
          </header>

          <ChatWindow messages={messages} onSuggestionClick={handleSuggestion} />

          <div className="shrink-0 border-t border-border bg-background/80 px-4 py-3 backdrop-blur">
            <div className="mx-auto max-w-3xl">
              <ChatInput
                onSend={handleSend}
                disabled={streaming}
                streaming={streaming}
              />
              <p className="mt-2 text-center text-[10px] text-muted-foreground">
                Responses cite their sources. Press{" "}
                <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono">
                  Enter
                </kbd>{" "}
                to send ·{" "}
                <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono">
                  Shift + Enter
                </kbd>{" "}
                for newline
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function normalizeCitations(
  raw?: Array<Record<string, unknown>>,
): Citation[] | undefined {
  if (!Array.isArray(raw) || raw.length === 0) return undefined;
  const normalized: Citation[] = [];
  for (const c of raw) {
    if (!c || typeof c !== "object") continue;
    const title =
      typeof c.title === "string"
        ? c.title
        : typeof c.source === "string"
          ? (c.source as string)
          : "Source";
    const source = typeof c.source === "string" ? (c.source as string) : "unknown";
    const url = typeof c.url === "string" ? (c.url as string) : undefined;
    const publicationDate =
      typeof c.publication_date === "string" && c.publication_date.length > 0
        ? (c.publication_date as string)
        : undefined;
    const ticker =
      typeof c.ticker === "string" && c.ticker.length > 0
        ? (c.ticker as string)
        : undefined;
    normalized.push({ title, source, url, publicationDate, ticker });
  }
  return normalized.length > 0 ? normalized : undefined;
}
