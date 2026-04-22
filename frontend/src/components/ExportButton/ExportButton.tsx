import { useState, useRef, useEffect } from "react";
import { Download, ChevronDown } from "lucide-react";

interface ExportButtonProps {
  ticker: string;
}

export default function ExportButton({ ticker }: ExportButtonProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleExport = (format: "csv" | "pdf") => {
    setOpen(false);
    const baseURL = import.meta.env.VITE_API_URL || "/api";
    const url = `${baseURL}/companies/${ticker}/sentiment?format=${format}`;

    const link = document.createElement("a");
    link.href = url;
    link.download = `${ticker}_sentiment.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-700"
      >
        <Download className="h-4 w-4" />
        Export
        <ChevronDown
          className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-40 rounded-lg border border-gray-700 bg-gray-800 py-1 shadow-xl">
          <button
            onClick={() => handleExport("csv")}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 transition-colors"
          >
            Export CSV
          </button>
          <button
            onClick={() => handleExport("pdf")}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 transition-colors"
          >
            Export PDF
          </button>
        </div>
      )}
    </div>
  );
}
