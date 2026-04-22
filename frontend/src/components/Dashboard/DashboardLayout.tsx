import type { ReactNode } from "react";
import Navbar from "@/components/common/Navbar";

interface DashboardLayoutProps {
  sidebar?: ReactNode;
  main: ReactNode;
  aside?: ReactNode;
}

export default function DashboardLayout({
  sidebar,
  main,
  aside,
}: DashboardLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-bg-primary)]">
      <Navbar />

      <div className="mx-auto flex w-full max-w-[1600px] flex-1 gap-5 px-5 py-4">
        {sidebar && (
          <aside className="hidden w-[260px] shrink-0 sm:block">
            <div className="sticky top-[60px] flex max-h-[calc(100vh-76px)] flex-col gap-4 overflow-y-auto">
              {sidebar}
            </div>
          </aside>
        )}

        <main className="min-w-0 flex-1">{main}</main>

        {aside && (
          <aside className="hidden w-[320px] shrink-0 xl:block">
            <div className="sticky top-[60px] flex max-h-[calc(100vh-76px)] flex-col gap-4 overflow-y-auto">
              {aside}
            </div>
          </aside>
        )}
      </div>

      <footer className="border-t border-[var(--color-border)] py-3 text-center text-[11px] text-[var(--color-text-muted)]">
        FinSentiment — Not financial advice. Data for educational purposes only.
      </footer>
    </div>
  );
}
