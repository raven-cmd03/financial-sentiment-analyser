import { useState, useCallback } from "react";
import { Brain, Play, Loader2 } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { getModels, getFinetuningJobs, startFinetuning } from "@/api/client";
import Navbar from "@/components/common/Navbar";
import DatasetSelector from "@/components/ModelManagement/DatasetSelector";
import HyperparamForm from "@/components/ModelManagement/HyperparamForm";
import type { HyperParams } from "@/components/ModelManagement/HyperparamForm";
import TrainingProgress from "@/components/ModelManagement/TrainingProgress";
import ModelComparison from "@/components/ModelManagement/ModelComparison";
import ActiveModelSwitcher from "@/components/ModelManagement/ActiveModelSwitcher";
import ErrorMessage from "@/components/common/ErrorMessage";

type Tab = "train" | "models";

const DEFAULT_HYPER: HyperParams = {
  learning_rate: 2e-5,
  batch_size: 16,
  epochs: 3,
  warmup_steps: 500,
  weight_decay: 0.01,
};

export default function ModelManagementPage() {
  const [tab, setTab] = useState<Tab>("train");
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [hyperParams, setHyperParams] = useState<HyperParams>(DEFAULT_HYPER);
  const [training, setTraining] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [trainError, setTrainError] = useState<string | null>(null);

  const {
    data: models,
    loading: modelsLoading,
    error: modelsError,
    refetch: refetchModels,
  } = useApi(() => getModels(), []);

  const {
    data: jobs,
    refetch: refetchJobs,
  } = useApi(() => getFinetuningJobs(), []);

  const runningJob = (jobs ?? []).find(
    (j) => j.status === "running" || j.status === "pending",
  );
  const displayJobId = activeJobId ?? runningJob?.id ?? null;

  const handleStartTraining = useCallback(async () => {
    if (!datasetId) return;
    setTraining(true);
    setTrainError(null);
    try {
      const job = await startFinetuning({
        dataset_name: datasetId,
        hyperparams: {
          learning_rate: hyperParams.learning_rate,
          batch_size: hyperParams.batch_size,
          epochs: hyperParams.epochs,
          warmup_steps: hyperParams.warmup_steps,
          weight_decay: hyperParams.weight_decay,
        },
      });
      setActiveJobId(job.id);
    } catch (err) {
      setTrainError(
        err instanceof Error ? err.message : "Failed to start training",
      );
    } finally {
      setTraining(false);
    }
  }, [datasetId, hyperParams]);

  const handleTrainingComplete = useCallback(() => {
    refetchModels();
    refetchJobs();
  }, [refetchModels, refetchJobs]);

  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-bg-primary)]">
      <Navbar />

      <div className="mx-auto w-full max-w-[960px] flex-1 px-5 py-4">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--color-accent)]/10">
            <Brain className="h-4.5 w-4.5 text-[var(--color-accent)]" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-[var(--color-text-primary)]">
              Model Management
            </h1>
            <p className="text-[12px] text-[var(--color-text-muted)]">
              Fine-tune FinBERT and manage model versions
            </p>
          </div>
        </div>

        <div className="mb-5 flex gap-0.5 rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] p-0.5">
          {(["train", "models"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 rounded-lg px-4 py-1.5 text-[13px] font-medium transition-all duration-150 ${
                tab === t
                  ? "bg-[var(--color-accent)]/12 text-[var(--color-accent-hover)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
              }`}
            >
              {t === "train" ? "Train Model" : "Models"}
            </button>
          ))}
        </div>

        {tab === "train" && (
          <div className="space-y-5">
            <DatasetSelector value={datasetId} onChange={setDatasetId} />
            <HyperparamForm values={hyperParams} onChange={setHyperParams} />

            {trainError && (
              <ErrorMessage
                message={trainError}
                onRetry={() => setTrainError(null)}
              />
            )}

            <button
              onClick={handleStartTraining}
              disabled={!datasetId || training || displayJobId !== null}
              className="flex items-center gap-2 rounded-[var(--radius-md)] bg-[var(--color-accent)] px-5 py-2 text-[13px] font-semibold text-white transition-all hover:bg-[var(--color-accent-hover)] disabled:opacity-40"
            >
              {training ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              Start Training
            </button>

            {displayJobId && (
              <TrainingProgress
                jobId={displayJobId}
                onComplete={handleTrainingComplete}
              />
            )}
          </div>
        )}

        {tab === "models" && (
          <div className="space-y-5">
            {modelsLoading ? (
              <div className="flex items-center justify-center py-14">
                <Loader2 className="h-5 w-5 animate-spin text-[var(--color-accent)]" />
              </div>
            ) : modelsError ? (
              <ErrorMessage message={modelsError} onRetry={refetchModels} />
            ) : (
              <>
                <ModelComparison models={models ?? []} />
                <div>
                  <h3 className="mb-3 text-[13px] font-semibold text-[var(--color-text-primary)]">
                    Switch Active Model
                  </h3>
                  <ActiveModelSwitcher
                    models={models ?? []}
                    onSwitch={refetchModels}
                  />
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
