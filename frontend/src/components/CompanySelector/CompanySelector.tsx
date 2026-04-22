import { useState, useMemo } from "react";
import { Search, Building2, Loader2 } from "lucide-react";
import { useAppContext } from "@/context/AppContext";

export default function CompanySelector() {
  const { companies, companiesLoading, selectedCompany, setSelectedCompany } =
    useAppContext();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!query.trim()) return companies;
    const lower = query.toLowerCase();
    return companies.filter(
      (c) =>
        c.name.toLowerCase().includes(lower) ||
        c.ticker.toLowerCase().includes(lower) ||
        c.sector.toLowerCase().includes(lower),
    );
  }, [companies, query]);

  const grouped = useMemo(() => {
    const map = new Map<string, typeof filtered>();
    for (const c of filtered) {
      const list = map.get(c.sector) ?? [];
      list.push(c);
      map.set(c.sector, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
      <div className="border-b border-[var(--color-border)] px-4 py-2.5">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Companies
        </h3>
      </div>

      <div className="px-3 pt-3 pb-1">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            type="text"
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-primary)] py-1.5 pl-8 pr-3 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none transition-colors focus:border-[var(--color-accent)]/50"
          />
        </div>
      </div>

      <div className="max-h-[520px] overflow-y-auto px-2 pb-2 pt-1">
        {companiesLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-4 w-4 animate-spin text-[var(--color-accent)]" />
          </div>
        ) : grouped.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-[var(--color-text-muted)]">
            No companies found
          </p>
        ) : (
          grouped.map(([sector, list]) => (
            <div key={sector} className="mb-2">
              <p className="mb-0.5 px-2 pt-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-text-muted)]/70">
                {sector}
              </p>
              {list.map((c) => {
                const active = selectedCompany === c.ticker;
                return (
                  <button
                    key={c.ticker}
                    onClick={() =>
                      setSelectedCompany(active ? null : c.ticker)
                    }
                    className={`flex w-full items-center gap-2 rounded-[var(--radius-md)] px-2 py-1.5 text-left transition-all duration-150 ${
                      active
                        ? "bg-[var(--color-accent)]/12 text-[var(--color-accent-hover)]"
                        : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]/50 hover:text-[var(--color-text-primary)]"
                    }`}
                  >
                    <Building2 className="h-3.5 w-3.5 shrink-0 opacity-40" />
                    <span className="text-xs font-semibold">{c.ticker}</span>
                    <span className="ml-auto truncate text-[11px] opacity-50">
                      {c.name}
                    </span>
                  </button>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
