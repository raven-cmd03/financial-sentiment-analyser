import { useEffect, useState } from "react";
import { Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import ThemeToggle from "./ThemeToggle";
import CommandPalette from "./CommandPalette";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  TrendingUp,
  MessageSquare,
  Brain,
  BarChart3,
  HelpCircle,
} from "lucide-react";

const mobileNav = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard, end: true },
  { label: "Trends", to: "/trends", icon: TrendingUp },
  { label: "Chat", to: "/chat", icon: MessageSquare },
  { label: "Models", to: "/models", icon: Brain },
  { label: "Onboarding", to: "/onboarding", icon: HelpCircle },
];

export default function TopBar() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur md:px-6">
      {/* Mobile hamburger → sheet with full nav. */}
      <Sheet>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-60 p-0">
          <div className="flex items-center gap-2 border-b p-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <BarChart3 className="h-4 w-4 text-primary" />
            </div>
            <span className="font-semibold tracking-tight">
              Fin<span className="text-primary">Sentiment</span>
            </span>
          </div>
          <nav className="flex flex-col gap-0.5 p-2">
            {mobileNav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-foreground hover:bg-accent",
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>
        </SheetContent>
      </Sheet>

      <div className="flex items-center gap-2 md:hidden">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
          <BarChart3 className="h-4 w-4 text-primary" />
        </div>
        <span className="text-sm font-semibold tracking-tight">
          Fin<span className="text-primary">Sentiment</span>
        </span>
      </div>

      {/* Desktop: global search (opens palette). */}
      <Button
        variant="outline"
        size="sm"
        onClick={() => setPaletteOpen(true)}
        className={cn(
          "ml-auto hidden h-9 min-w-[280px] justify-between text-muted-foreground md:flex",
        )}
      >
        <span className="flex items-center gap-2">
          <Search className="h-4 w-4" />
          Search companies, pages…
        </span>
        <kbd className="pointer-events-none hidden items-center gap-1 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] opacity-70 lg:inline-flex">
          ⌘K
        </kbd>
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={() => setPaletteOpen(true)}
        aria-label="Open search"
      >
        <Search className="h-4 w-4" />
      </Button>

      <div className="ml-auto flex items-center gap-1 md:ml-2">
        <ThemeToggle compact />
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </header>
  );
}
