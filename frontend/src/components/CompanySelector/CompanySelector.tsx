import { useState, useMemo } from "react";
import { Search, Building2 } from "lucide-react";
import { useAppContext } from "@/context/AppContext";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

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
        (c.sector ?? "").toLowerCase().includes(lower),
    );
  }, [companies, query]);

  const grouped = useMemo(() => {
    const map = new Map<string, typeof filtered>();
    for (const c of filtered) {
      const sector = c.sector ?? "Other";
      const list = map.get(sector) ?? [];
      list.push(c);
      map.set(sector, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-3 p-4">
        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Companies
        </CardTitle>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search companies…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-8 pl-8 text-xs"
            aria-label="Search companies"
          />
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[520px]">
          <div className="px-2 pb-3">
            {companiesLoading ? (
              <div className="space-y-2 px-2 py-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : grouped.length === 0 ? (
              <p className="px-2 py-8 text-center text-xs text-muted-foreground">
                No companies match “{query}”.
              </p>
            ) : (
              grouped.map(([sector, list]) => (
                <div key={sector} className="mt-2 first:mt-0">
                  <p className="sticky top-0 z-10 -mx-2 bg-card/95 px-4 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground backdrop-blur">
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
                        className={cn(
                          "mt-0.5 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors",
                          active
                            ? "bg-primary/10 text-primary"
                            : "text-foreground hover:bg-accent",
                        )}
                      >
                        <Building2 className="h-3.5 w-3.5 shrink-0 opacity-50" />
                        <span className="text-xs font-semibold tabular-nums">
                          {c.ticker}
                        </span>
                        <span className="ml-auto truncate text-[11px] text-muted-foreground">
                          {c.name}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
