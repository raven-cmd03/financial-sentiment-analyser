import { Sliders } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface HyperParams {
  learning_rate: number;
  batch_size: number;
  epochs: number;
  warmup_steps: number;
  weight_decay: number;
}

interface HyperparamFormProps {
  values: HyperParams;
  onChange: (values: HyperParams) => void;
}

const FIELDS: {
  key: keyof HyperParams;
  label: string;
  min: number;
  max: number;
  step: number;
}[] = [
  { key: "learning_rate", label: "Learning rate", min: 1e-6, max: 1e-2, step: 1e-6 },
  { key: "batch_size", label: "Batch size", min: 1, max: 128, step: 1 },
  { key: "epochs", label: "Epochs", min: 1, max: 50, step: 1 },
  { key: "warmup_steps", label: "Warmup steps", min: 0, max: 5000, step: 50 },
  { key: "weight_decay", label: "Weight decay", min: 0, max: 1, step: 0.001 },
];

export default function HyperparamForm({
  values,
  onChange,
}: HyperparamFormProps) {
  const update = (key: keyof HyperParams, raw: string) => {
    const num = parseFloat(raw);
    if (!Number.isNaN(num)) {
      onChange({ ...values, [key]: num });
    }
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2 space-y-0 pb-3">
        <Sliders className="h-4 w-4 text-primary" />
        <CardTitle className="text-sm">Hyperparameters</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FIELDS.map((f) => (
            <div key={f.key} className="space-y-1.5">
              <Label
                htmlFor={`hp-${f.key}`}
                className="text-xs text-muted-foreground"
              >
                {f.label}
              </Label>
              <Input
                id={`hp-${f.key}`}
                type="number"
                value={values[f.key]}
                min={f.min}
                max={f.max}
                step={f.step}
                onChange={(e) => update(f.key, e.target.value)}
              />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export type { HyperParams };
