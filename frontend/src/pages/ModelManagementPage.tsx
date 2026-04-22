import { useCallback, useState } from "react";
import { Brain, Play, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { getModels, getFinetuningJobs, startFinetuning } from "@/api/client";
import DatasetSelector from "@/components/ModelManagement/DatasetSelector";
import HyperparamForm from "@/components/ModelManagement/HyperparamForm";
import type { HyperParams } from "@/components/ModelManagement/HyperparamForm";
import TrainingProgress from "@/components/ModelManagement/TrainingProgress";
import ModelComparison from "@/components/ModelManagement/ModelComparison";
import ActiveModelSwitcher from "@/components/ModelManagement/ActiveModelSwitcher";
import ErrorMessage from "@/components/common/ErrorMessage";
import LockedStateCard from "@/components/common/LockedStateCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const DEFAULT_HYPER: HyperParams = {
  learning_rate: 2e-5,
  batch_size: 16,
  epochs: 3,
  warmup_steps: 500,
  weight_decay: 0.01,
};

export default function ModelManagementPage() {
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [hyperParams, setHyperParams] = useState<HyperParams>(DEFAULT_HYPER);
  const [training, setTraining] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [trainError, setTrainError] = useState<string | null>(null);

  const {
    data: models,
    loading: modelsLoading,
    error: modelsError,
    locked: modelsLocked,
    refetch: refetchModels,
  } = useApi(() => getModels(), []);

  const {
    data: jobs,
    locked: jobsLocked,
    refetch: refetchJobs,
  } = useApi(() => getFinetuningJobs(), []);

  const locked = modelsLocked || jobsLocked;

  const runningJob = (jobs ?? []).find(
    (j) => j.status === "running" || j.status === "pending",
  );
  const displayJobId = activeJobId ?? (runningJob ? String(runningJob.id) : null);

  const handleStartTraining = useCallback(async () => {
    if (!datasetId) return;
    setTraining(true);
    setTrainError(null);
    try {
      const job = await startFinetuning({
        dataset_name: datasetId,
        hyperparams: { ...hyperParams },
      });
      setActiveJobId(String(job.id));
      toast.success("Fine-tuning started", {
        description: `Job #${job.id} · ${datasetId}`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start training";
      setTrainError(msg);
    } finally {
      setTraining(false);
    }
  }, [datasetId, hyperParams]);

  const handleTrainingComplete = useCallback(() => {
    refetchModels();
    refetchJobs();
  }, [refetchModels, refetchJobs]);

  return (
    <div className="mx-auto w-full max-w-5xl p-6">
      <header className="mb-6 flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Brain className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Model Management
          </h1>
          <p className="text-sm text-muted-foreground">
            Fine-tune FinBERT and manage model versions
          </p>
        </div>
      </header>

      {locked ? (
        <LockedStateCard
          title="Model Management is locked"
          description="Training and model endpoints require an API_KEY. Configure the backend API_KEY env var and VITE_API_KEY on the frontend to unlock this page."
          onRetry={() => {
            refetchModels();
            refetchJobs();
          }}
        />
      ) : (
        <Tabs defaultValue="train" className="space-y-6">
          <TabsList className="grid w-full max-w-sm grid-cols-2">
            <TabsTrigger value="train">Train</TabsTrigger>
            <TabsTrigger value="models">Models</TabsTrigger>
          </TabsList>

          <TabsContent value="train" className="space-y-5">
            <DatasetSelector value={datasetId} onChange={setDatasetId} />
            <HyperparamForm values={hyperParams} onChange={setHyperParams} />

            {trainError && (
              <ErrorMessage
                message={trainError}
                onRetry={() => setTrainError(null)}
              />
            )}

            <div>
              <Button
                onClick={handleStartTraining}
                disabled={!datasetId || training || displayJobId !== null}
                className="gap-2"
              >
                {training ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                Start training
              </Button>
            </div>

            {displayJobId && (
              <TrainingProgress
                jobId={displayJobId}
                onComplete={handleTrainingComplete}
              />
            )}
          </TabsContent>

          <TabsContent value="models" className="space-y-5">
            {modelsLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-24 w-full" />
              </div>
            ) : modelsError ? (
              <ErrorMessage message={modelsError} onRetry={refetchModels} />
            ) : (
              <>
                <ModelComparison models={models ?? []} />
                <ActiveModelSwitcher
                  models={models ?? []}
                  onSwitch={refetchModels}
                />
              </>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
