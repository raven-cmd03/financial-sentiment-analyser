import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { getCompanies } from "@/api/client";
import type { Company } from "@/types";

interface Filters {
  sentiment: string;
  source: string;
}

interface DateRange {
  start: Date;
  end: Date;
}

interface AppContextValue {
  selectedCompany: string | null;
  setSelectedCompany: (ticker: string | null) => void;
  dateRange: DateRange;
  setDateRange: (range: DateRange) => void;
  filters: Filters;
  setFilters: (filters: Filters) => void;
  companies: Company[];
  companiesLoading: boolean;
  refreshCompanies: () => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<DateRange>({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    end: new Date(),
  });
  const [filters, setFilters] = useState<Filters>({
    sentiment: "all",
    source: "all",
  });
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);

  const refreshCompanies = useCallback(() => {
    setCompaniesLoading(true);
    getCompanies()
      .then(setCompanies)
      .catch((err) => console.error("Failed to fetch companies:", err))
      .finally(() => setCompaniesLoading(false));
  }, []);

  useEffect(() => {
    refreshCompanies();
  }, [refreshCompanies]);

  return (
    <AppContext.Provider
      value={{
        selectedCompany,
        setSelectedCompany,
        dateRange,
        setDateRange,
        filters,
        setFilters,
        companies,
        companiesLoading,
        refreshCompanies,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
}
