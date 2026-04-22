import { useState } from "react";
import { Upload, Database, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { getDatasets, uploadDataset } from "@/api/client";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  RadioGroup,
  RadioGroupItem,
} from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

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
      toast.success("Dataset uploaded", {
        description: `${ds.name} · ${ds.sample_count.toLocaleString()} samples`,
      });
    } catch (err) {
      toast.error("Upload failed", {
        description: (err as Error).message,
      });
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0 pb-3">
        <Database className="h-4 w-4 text-primary" />
        <CardTitle className="text-sm">Training dataset</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <RadioGroup
          value={value ?? ""}
          onValueChange={(v) => onChange(v)}
          className="gap-2"
        >
          {BUILTIN_DATASETS.map((ds) => (
            <Label
              key={ds.key}
              htmlFor={`ds-${ds.key}`}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal transition-colors",
                value === ds.key
                  ? "border-primary/60 bg-primary/5"
                  : "border-border hover:border-border hover:bg-accent/40",
              )}
            >
              <RadioGroupItem id={`ds-${ds.key}`} value={ds.key} className="mt-0.5" />
              <div>
                <p className="text-sm font-medium text-foreground">{ds.label}</p>
                <p className="text-xs text-muted-foreground">{ds.description}</p>
              </div>
            </Label>
          ))}

          {(customDatasets ?? []).map((ds) => (
            <Label
              key={ds.name}
              htmlFor={`ds-${ds.name}`}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal transition-colors",
                value === ds.name
                  ? "border-primary/60 bg-primary/5"
                  : "border-border hover:border-border hover:bg-accent/40",
              )}
            >
              <RadioGroupItem id={`ds-${ds.name}`} value={ds.name} className="mt-0.5" />
              <div>
                <p className="text-sm font-medium text-foreground">{ds.name}</p>
                <p className="text-xs text-muted-foreground">{ds.description}</p>
              </div>
            </Label>
          ))}
        </RadioGroup>

        <label
          className={cn(
            "flex cursor-pointer items-center gap-3 rounded-md border border-dashed p-3 transition-colors",
            uploading
              ? "border-primary/60 bg-primary/5"
              : "border-border hover:border-primary/50",
          )}
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          ) : (
            <Upload className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="text-xs text-muted-foreground">
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
      </CardContent>
    </Card>
  );
}
