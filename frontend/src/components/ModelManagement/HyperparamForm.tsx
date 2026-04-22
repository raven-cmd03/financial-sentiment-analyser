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
  { key: "learning_rate", label: "Learning Rate", min: 1e-6, max: 1e-2, step: 1e-6 },
  { key: "batch_size", label: "Batch Size", min: 1, max: 128, step: 1 },
  { key: "epochs", label: "Epochs", min: 1, max: 50, step: 1 },
  { key: "warmup_steps", label: "Warmup Steps", min: 0, max: 5000, step: 50 },
  { key: "weight_decay", label: "Weight Decay", min: 0, max: 1, step: 0.001 },
];

export default function HyperparamForm({
  values,
  onChange,
}: HyperparamFormProps) {
  const update = (key: keyof HyperParams, raw: string) => {
    const num = parseFloat(raw);
    if (!isNaN(num)) {
      onChange({ ...values, [key]: num });
    }
  };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-4">
      <label className="mb-3 block text-[13px] font-semibold text-[var(--color-text-primary)]">
        Hyperparameters
      </label>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label className="mb-1 block text-[11px] font-medium text-[var(--color-text-muted)]">
              {f.label}
            </label>
            <input
              type="number"
              value={values[f.key]}
              min={f.min}
              max={f.max}
              step={f.step}
              onChange={(e) => update(f.key, e.target.value)}
              className="w-full rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg-primary)] px-3 py-1.5 text-[13px] text-[var(--color-text-primary)] outline-none transition-colors focus:border-[var(--color-accent)]/50"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export type { HyperParams };
