import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  TrendingUp,
  MessageSquare,
  Settings,
  BarChart3,
} from "lucide-react";

interface NavItem {
  label: string;
  path: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { label: "Dashboard", path: "/", icon: <LayoutDashboard size={16} /> },
  { label: "Trends", path: "/trends", icon: <TrendingUp size={16} /> },
  { label: "Chat", path: "/chat", icon: <MessageSquare size={16} /> },
  { label: "Models", path: "/models", icon: <Settings size={16} /> },
];

export default function Navbar() {
  const { pathname } = useLocation();

  return (
    <nav className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg-primary)]/90 backdrop-blur-xl">
      <div className="mx-auto flex h-12 max-w-[1600px] items-center justify-between px-5">
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--color-accent)]/15">
            <BarChart3 className="h-4 w-4 text-[var(--color-accent)] transition-transform group-hover:scale-110" />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-[var(--color-text-primary)]">
            Fin<span className="text-[var(--color-accent)]">Sentiment</span>
          </span>
        </Link>

        <div className="flex items-center gap-0.5">
          {navItems.map((item) => {
            const isActive =
              item.path === "/"
                ? pathname === "/"
                : pathname.startsWith(item.path);

            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all duration-150 ${
                  isActive
                    ? "bg-[var(--color-accent)]/12 text-[var(--color-accent-hover)]"
                    : "text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)]/50 hover:text-[var(--color-text-secondary)]"
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
