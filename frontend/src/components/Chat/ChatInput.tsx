import { useState, useRef, useEffect } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  streaming?: boolean;
}

export default function ChatInput({
  onSend,
  disabled,
  streaming,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        200,
      )}px`;
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="relative flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm transition-all focus-within:border-primary/50 focus-within:shadow-md focus-within:ring-2 focus-within:ring-primary/10">
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about financial sentiment…"
        disabled={disabled}
        rows={1}
        className="min-h-[40px] resize-none border-0 bg-transparent px-2 py-2 text-sm shadow-none placeholder:text-muted-foreground focus-visible:ring-0"
      />
      <Button
        onClick={handleSubmit}
        disabled={!canSend}
        size="icon"
        className="h-9 w-9 shrink-0 rounded-xl"
        aria-label={streaming ? "Streaming response" : "Send message"}
      >
        {streaming ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <ArrowUp className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
}
