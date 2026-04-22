import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

interface ThemeToggleProps {
  compact?: boolean;
}

/**
 * Button that flips between dark and light. Delays rendering until mounted
 * so the server/client class mismatch (next-themes) doesn't flash.
 */
export default function ThemeToggle({ compact = false }: ThemeToggleProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";
  const nextLabel = isDark ? "Switch to light mode" : "Switch to dark mode";

  const Icon = isDark ? Sun : Moon;

  if (compact) {
    return (
      <Button
        variant="ghost"
        size="icon"
        aria-label={nextLabel}
        onClick={() => setTheme(isDark ? "light" : "dark")}
      >
        <Icon className="h-4 w-4" />
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      className="w-full justify-start gap-2"
      aria-label={nextLabel}
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      <Icon className="h-4 w-4" />
      <span className="text-sm">{isDark ? "Light mode" : "Dark mode"}</span>
    </Button>
  );
}
