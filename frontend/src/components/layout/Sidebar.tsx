import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  TrendingUp,
  MessageSquare,
  Brain,
  BarChart3,
  HelpCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import ThemeToggle from "./ThemeToggle";

interface NavItem {
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  end?: boolean;
}

const primaryNav: NavItem[] = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard, end: true },
  { label: "Trends", to: "/trends", icon: TrendingUp },
  { label: "Chat", to: "/chat", icon: MessageSquare },
  { label: "Models", to: "/models", icon: Brain },
];

const secondaryNav: NavItem[] = [
  { label: "Onboarding", to: "/onboarding", icon: HelpCircle },
];

function NavButton({ item }: { item: NavItem }) {
  const Icon = item.icon;
  return (
    <Tooltip delayDuration={200}>
      <TooltipTrigger asChild>
        <NavLink
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "group flex h-10 w-10 items-center justify-center rounded-lg transition-colors",
              "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              isActive &&
                "bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary",
            )
          }
          aria-label={item.label}
        >
          <Icon className="h-[18px] w-[18px]" />
        </NavLink>
      </TooltipTrigger>
      <TooltipContent side="right" sideOffset={8}>
        {item.label}
      </TooltipContent>
    </Tooltip>
  );
}

export default function Sidebar() {
  return (
    <aside
      aria-label="Primary navigation"
      className="hidden h-screen w-16 shrink-0 flex-col items-center border-r border-sidebar-border bg-sidebar py-4 md:flex"
    >
      <NavLink
        to="/"
        className="mb-6 flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary transition-transform hover:scale-[1.03]"
        aria-label="FinSentiment home"
      >
        <BarChart3 className="h-5 w-5" />
      </NavLink>

      <nav className="flex flex-col gap-1">
        {primaryNav.map((item) => (
          <NavButton key={item.to} item={item} />
        ))}
      </nav>

      <div className="mt-auto flex flex-col items-center gap-1">
        {secondaryNav.map((item) => (
          <NavButton key={item.to} item={item} />
        ))}
        <ThemeToggle compact />
      </div>
    </aside>
  );
}
