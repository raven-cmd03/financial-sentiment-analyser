import { useState } from "react";
import { Upload, Database } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { getDatasets, uploadDataset } from "@/api/client";

interface DatasetSelectorProps {
  value: string | null;
  onChange: (datasetId: string) => void;
}

interface BuiltinDataset {
  key: string;
  label: string;
  description: string;
}

const BUILTIN_DATASETS: BuiltinDataset[] = [
  {
    key: "financial_phrasebank",
    label: "Financial PhraseBank",
    description: "4,840 financial news sentences labeled by domain experts",
  },
  {
    key: "fintweet-sentiment-2025",
    label: "FinTweet Sentiment",
    description: "Finance-related tweets with sentiment annotations",
  },
];

export default function DatasetSelector({
  value,
  onChange,
}: DatasetSelectorProps) {
  const { data: customDatasets, refetch } = useApi(() => getDatasets(), []);
  const [uploading, setUploading] = useState(false);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const ds = await uploadDataset(file);
      refetch();
      onChange(ds.name);
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
      <label className="mb-3 flex items-center gap-1.5 text-[13px] font-semibold text-[var(--color-text-primary)]">
        <Database className="h-3.5 w-3.5 text-[var(--color-accent)]" />
        Training Dataset
      </label>

      <div className="space-y-2">
        {BUILTIN_DATASETS.map((ds) => (
          <label
            key={ds.key}
            className={`flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border p-3 transition-all duration-150 ${
              value === ds.key
                ? "border-[var(--color-accent)]/40 bg-[var(--color-accent)]/8"
                : "border-[var(--color-border)] hover:border-[var(--color-border)]/80 hover:bg-[var(--color-bg-tertiary)]/30"
            }`}
          >
            <input
              type="radio"
              name="dataset"
              value={ds.key}
              checked={value === ds.key}
              onChange={() => onChange(ds.key)}
              className="mt-0.5 accent-[var(--color-accent)]"
            />
            <div>
              <p className="text-[13px] font-medium text-[var(--color-text-primary)]">
                {ds.label}
              </p>
              <p className="text-[11px] text-[var(--color-text-muted)]">
                {ds.description}
              </p>
            </div>
          </label>
        ))}

        {(customDatasets ?? []).map((ds) => (
          <label
            key={ds.name}
            className={`flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border p-3 transition-all duration-150 ${
              value === ds.name
                ? "border-[var(--color-accent)]/40 bg-[var(--color-accent)]/8"
                : "border-[var(--color-border)] hover:border-[var(--color-border)]/80 hover:bg-[var(--color-bg-tertiary)]/30"
            }`}
          >
            <input
              type="radio"
              name="dataset"
              value={ds.name}
              checked={value === ds.name}
              onChange={() => onChange(ds.name)}
              className="mt-0.5 accent-[var(--color-accent)]"
            />
            <div>
              <p className="text-[13px] font-medium text-[var(--color-text-primary)]">
                {ds.name}
              </p>
              <p className="text-[11px] text-[var(--color-text-muted)]">
                {ds.description}
              </p>
            </div>
          </label>
        ))}

        <label
          className={`flex cursor-pointer items-center gap-3 rounded-[var(--radius-md)] border border-dashed p-3 transition-all duration-150 ${
            uploading
              ? "border-[var(--color-accent)]/40 bg-[var(--color-accent)]/8"
              : "border-[var(--color-border)] hover:border-[var(--color-accent)]/30"
          }`}
        >
          <Upload className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
          <span className="text-[12px] text-[var(--color-text-muted)]">
            {uploading ? "Uploading…" : "Upload custom dataset (.csv)"}
          </span>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
          />
        </label>
      </div>
    </div>
  );
}
