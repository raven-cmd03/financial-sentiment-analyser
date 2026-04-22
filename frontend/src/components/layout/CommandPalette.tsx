import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  TrendingUp,
  MessageSquare,
  Brain,
  Building2,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useAppContext } from "@/context/AppContext";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Cmd/Ctrl-K command palette. Lets the user jump to a page or pick any
 * tracked company by ticker/name/sector. Parent owns the open state.
 */
export default function CommandPalette({
  open,
  onOpenChange,
}: CommandPaletteProps) {
  const navigate = useNavigate();
  const { companies, setSelectedCompany } = useAppContext();
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const go = (to: string) => {
    onOpenChange(false);
    navigate(to);
  };

  const pickCompany = (ticker: string) => {
    setSelectedCompany(ticker);
    go(`/companies/${ticker}`);
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        placeholder="Search companies, pages…"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigation">
          <CommandItem onSelect={() => go("/")}>
            <LayoutDashboard className="mr-2 h-4 w-4" />
            Dashboard
          </CommandItem>
          <CommandItem onSelect={() => go("/trends")}>
            <TrendingUp className="mr-2 h-4 w-4" />
            Trends
          </CommandItem>
          <CommandItem onSelect={() => go("/chat")}>
            <MessageSquare className="mr-2 h-4 w-4" />
            Chat
          </CommandItem>
          <CommandItem onSelect={() => go("/models")}>
            <Brain className="mr-2 h-4 w-4" />
            Model Management
          </CommandItem>
        </CommandGroup>

        {companies.length > 0 && (
          <CommandGroup heading="Companies">
            {companies.slice(0, 50).map((c) => (
              <CommandItem
                key={c.ticker}
                value={`${c.ticker} ${c.name} ${c.sector ?? ""}`}
                onSelect={() => pickCompany(c.ticker)}
              >
                <Building2 className="mr-2 h-4 w-4" />
                <span className="font-mono text-xs text-muted-foreground">
                  {c.ticker}
                </span>
                <span className="ml-2 truncate">{c.name}</span>
                {c.sector && (
                  <span className="ml-auto text-xs text-muted-foreground">
                    {c.sector}
                  </span>
                )}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
