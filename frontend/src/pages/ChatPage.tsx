import { useState, useCallback, useEffect, useRef } from "react";
import { MessageSquare } from "lucide-react";
import Navbar from "@/components/common/Navbar";
import {
  createChatSession,
  getChatSessions,
  getChatSession,
  sendChatMessageUrl,
  deleteChatSession,
  getApiKey,
} from "@/api/client";
import SessionList from "@/components/Chat/SessionList";
import ChatWindow from "@/components/Chat/ChatWindow";
import ChatInput from "@/components/Chat/ChatInput";
import type { DisplayMessage } from "@/components/Chat/ChatWindow";
import type { ChatSession } from "@/types";
import type { Citation } from "@/components/Chat/CitationCard";

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | number | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const data = await getChatSessions();
      setSessions(data);
    } catch {
      /* swallow */
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
        } catch {
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
                    content: "Sorry, an error occurred. Please try again.",
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

  return (
    <div className="flex h-screen flex-col bg-[var(--color-bg-primary)]">
      <Navbar />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex w-[240px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
          <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-3">
            <MessageSquare className="h-4 w-4 text-[var(--color-accent)]" />
            <h2 className="text-[12px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              Chats
            </h2>
          </div>
          <SessionList
            sessions={sessions}
            activeId={activeId}
            onSelect={selectSession}
            onCreate={handleCreate}
            onDelete={handleDelete}
          />
        </div>

        <div className="flex flex-1 flex-col">
          <ChatWindow messages={messages} onSuggestionClick={handleSuggestion} />
          <div className="border-t border-[var(--color-border)] bg-[var(--color-bg-primary)] px-4 py-3">
            <div className="mx-auto max-w-3xl">
              <ChatInput onSend={handleSend} disabled={streaming} />
            </div>
          </div>
        </div>
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
    normalized.push({ title, source, url });
  }
  return normalized.length > 0 ? normalized : undefined;
}
