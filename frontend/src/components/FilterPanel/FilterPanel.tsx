import { RotateCcw } from "lucide-react";
import { useAppContext } from "@/context/AppContext";

const SENTIMENTS = ["all", "positive", "negative", "neutral"] as const;

const SOURCES = [
  "all",
  "Reuters",
  "Bloomberg",
  "CNBC",
  "MarketWatch",
  "Yahoo Finance",
  "Financial Times",
] as const;

export default function FilterPanel() {
  const { dateRange, setDateRange, filters, setFilters } = useAppContext();

  const handleReset = () => {
    setDateRange({
      start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
      end: new Date(),
    });
    setFilters({ sentiment: "all", source: "all" });
  };

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-200">Filters</h3>
        <button
          onClick={handleReset}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
      </div>

      {/* Date range */}
      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-400">
          Date Range
        </label>
        <div className="grid grid-cols-2 gap-2">
          <input
            type="date"
            value={dateRange.start.toISOString().slice(0, 10)}
            onChange={(e) =>
              setDateRange({ ...dateRange, start: new Date(e.target.value) })
            }
            className="rounded-md border border-gray-600 bg-gray-900 px-3 py-1.5 text-xs text-gray-200 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <input
            type="date"
            value={dateRange.end.toISOString().slice(0, 10)}
            onChange={(e) =>
              setDateRange({ ...dateRange, end: new Date(e.target.value) })
            }
            className="rounded-md border border-gray-600 bg-gray-900 px-3 py-1.5 text-xs text-gray-200 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Sentiment filter */}
      <div className="mt-4 space-y-2">
        <label className="block text-xs font-medium text-gray-400">
          Sentiment
        </label>
        <div className="flex flex-wrap gap-1.5">
          {SENTIMENTS.map((s) => (
            <button
              key={s}
              onClick={() => setFilters({ ...filters, sentiment: s })}
              className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
                filters.sentiment === s
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Source filter */}
      <div className="mt-4 space-y-2">
        <label className="block text-xs font-medium text-gray-400">
          Source
        </label>
        <select
          value={filters.source}
          onChange={(e) => setFilters({ ...filters, source: e.target.value })}
          className="w-full rounded-md border border-gray-600 bg-gray-900 px-3 py-1.5 text-xs text-gray-200 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        >
          {SOURCES.map((src) => (
            <option key={src} value={src}>
              {src === "all" ? "All Sources" : src}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
