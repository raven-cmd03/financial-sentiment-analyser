import { useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { activateModel } from "@/api/client";
import type { ModelInfo } from "@/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ActiveModelSwitcherProps {
  models: ModelInfo[];
  onSwitch: () => void;
}

export default function ActiveModelSwitcher({
  models,
  onSwitch,
}: ActiveModelSwitcherProps) {
  const [activating, setActivating] = useState<string | null>(null);

  const handleActivate = async (id: string, name: string) => {
    setActivating(id);
    try {
      await activateModel(id);
      toast.success(`Activated ${name}`);
      onSwitch();
    } catch (err) {
      toast.error("Activation failed", {
        description: (err as Error).message,
      });
    } finally {
      setActivating(null);
    }
  };

  if (models.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Active model</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {models.map((m) => (
          <div
            key={m.id}
            className={cn(
              "flex items-center justify-between rounded-md border p-3 transition-colors",
              m.is_active
                ? "border-primary/60 bg-primary/5"
                : "border-border bg-background",
            )}
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">
                {m.name}
              </p>
              <p className="text-xs capitalize text-muted-foreground">
                {m.source}
                {m.accuracy != null &&
                  ` · ${(m.accuracy * 100).toFixed(1)}% acc`}
              </p>
            </div>

            {m.is_active ? (
              <span className="flex items-center gap-1.5 text-xs font-medium text-primary">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Active
              </span>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleActivate(m.id, m.name)}
                disabled={activating !== null}
              >
                {activating === m.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  "Activate"
                )}
              </Button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
