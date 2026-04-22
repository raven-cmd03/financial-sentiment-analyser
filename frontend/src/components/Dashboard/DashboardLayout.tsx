import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface DashboardLayoutProps {
  sidebar?: ReactNode;
  main: ReactNode;
  aside?: ReactNode;
  className?: string;
}

/**
 * Content-level layout within the AppShell: optional left rail for a widget
 * (e.g. CompanySelector), main column, optional right rail.
 */
export default function DashboardLayout({
  sidebar,
  main,
  aside,
  className,
}: DashboardLayoutProps) {
  return (
    <div
      className={cn(
        "mx-auto flex w-full max-w-[1600px] gap-6 px-4 py-6 md:px-6",
        className,
      )}
    >
      {sidebar && (
        <aside className="hidden w-[280px] shrink-0 lg:block">
          <div className="sticky top-20 flex max-h-[calc(100vh-6rem)] flex-col gap-4 overflow-y-auto">
            {sidebar}
          </div>
        </aside>
      )}

      <main className="min-w-0 flex-1">{main}</main>

      {aside && (
        <aside className="hidden w-[320px] shrink-0 xl:block">
          <div className="sticky top-20 flex max-h-[calc(100vh-6rem)] flex-col gap-4 overflow-y-auto">
            {aside}
          </div>
        </aside>
      )}
    </div>
  );
}
