import { useState } from "react";
import { CheckCircle, Loader2 } from "lucide-react";
import { activateModel } from "@/api/client";
import type { ModelInfo } from "@/types";

interface ActiveModelSwitcherProps {
  models: ModelInfo[];
  onSwitch: () => void;
}

export default function ActiveModelSwitcher({
  models,
  onSwitch,
}: ActiveModelSwitcherProps) {
  const [activating, setActivating] = useState<string | null>(null);

  const handleActivate = async (id: string) => {
    setActivating(id);
    try {
      await activateModel(id);
      onSwitch();
    } catch (err) {
      console.error("Failed to activate model:", err);
    } finally {
      setActivating(null);
    }
  };

  return (
    <div className="space-y-2">
      {models.map((m) => (
        <div
          key={m.id}
          className={`flex items-center justify-between rounded-lg border p-3 transition-colors ${
            m.is_active
              ? "border-blue-500/50 bg-blue-500/10"
              : "border-gray-700 bg-gray-800"
          }`}
        >
          <div>
            <p className="text-sm font-medium text-gray-200">{m.name}</p>
            <p className="text-xs text-gray-500">
              {m.base_model} · v{m.version}
              {m.accuracy !== undefined &&
                ` · ${(m.accuracy * 100).toFixed(1)}% acc`}
            </p>
          </div>

          {m.is_active ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-blue-400">
              <CheckCircle className="h-3.5 w-3.5" />
              Active
            </span>
          ) : (
            <button
              onClick={() => handleActivate(m.id)}
              disabled={activating !== null}
              className="rounded-md bg-gray-700 px-3 py-1.5 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-600 disabled:opacity-50"
            >
              {activating === m.id ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                "Activate"
              )}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
