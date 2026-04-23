import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from datasets import Dataset, load_dataset
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from transformers import (
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

from app.config import get_settings
from app.models import FinetuningJob
from app.services.sentiment_analyzer import _load_model, _load_tokenizer

logger = logging.getLogger(__name__)
settings = get_settings()

AVAILABLE_DATASETS = [
    {
        "name": "financial_phrasebank",
        "hf_path": "financial_phrasebank",
        "hf_config": "sentences_allagree",
        "description": "~4,800 English financial news sentences labeled positive / negative / neutral "
        "(100 % annotator agreement split).",
        "labels": ["negative", "neutral", "positive"],
        # Dataset label index → canonical app label. Used to write
        # model.config.id2label at save time so downstream inference
        # doesn't inherit a stale map from the base checkpoint.
        "canonical_labels": {0: "Negative", 1: "Neutral", 2: "Positive"},
    },
    {
        "name": "fintweet-sentiment-2025",
        "hf_path": "zeroshot/twitter-financial-news-sentiment",
        "hf_config": None,
        "description": "Financial tweets labeled with sentiment — useful for social-media domain adaptation.",
        "labels": ["bearish", "bullish", "neutral"],
        # 0=Bearish→Negative, 1=Bullish→Positive, 2=Neutral→Neutral
        "canonical_labels": {0: "Negative", 1: "Positive", 2: "Neutral"},
    },
]


def _compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1": f1_score(labels, preds, average="weighted"),
        "precision": precision_score(labels, preds, average="weighted", zero_division=0),
        "recall": recall_score(labels, preds, average="weighted", zero_division=0),
    }


class _ProgressCallback(TrainerCallback):
    """Writes training metrics back to the DB after each evaluation."""

    def __init__(self, session, job_id: int):
        self._session = session
        self._job_id = job_id

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics is None:
            return
        try:
            job = self._session.query(FinetuningJob).filter_by(id=self._job_id).first()
            if job:
                stored = dict(job.metrics or {})
                stored.update(
                    {
                        "epoch": state.epoch,
                        "step": state.global_step,
                        **{k: round(v, 6) for k, v in metrics.items() if isinstance(v, (int, float))},
                    }
                )
                job.metrics = stored
                self._session.commit()
        except Exception:
            logger.exception("Failed to persist training metrics for job %d", self._job_id)


class FineTuningPipeline:
    def __init__(self, session=None):
        self._session = session

    # ------------------------------------------------------------------
    # Dataset helpers
    # ------------------------------------------------------------------

    @staticmethod
    def download_dataset(name: str) -> Dataset:
        meta = next((d for d in AVAILABLE_DATASETS if d["name"] == name), None)
        if meta is None:
            raise ValueError(f"Unknown dataset: {name}. Available: {[d['name'] for d in AVAILABLE_DATASETS]}")

        logger.info("Downloading dataset %s from HuggingFace", meta["hf_path"])
        ds = load_dataset(
            meta["hf_path"],
            meta["hf_config"],
            cache_dir=settings.DATASET_DIR,
            trust_remote_code=True,
        )
        if isinstance(ds, dict):
            ds = ds["train"] if "train" in ds else list(ds.values())[0]
        return ds

    @staticmethod
    def prepare_dataset(dataset: Dataset, tokenizer) -> dict[str, Dataset]:
        """Tokenise and split into 80 / 10 / 10."""

        def tokenize(batch):
            text_col = "sentence" if "sentence" in batch else "text"
            return tokenizer(batch[text_col], truncation=True, padding="max_length", max_length=128)

        dataset = dataset.map(tokenize, batched=True, remove_columns=[
            c for c in dataset.column_names if c not in ("label", "input_ids", "attention_mask")
        ])
        dataset.set_format("torch")

        split_1 = dataset.train_test_split(test_size=0.2, seed=42)
        val_test = split_1["test"].train_test_split(test_size=0.5, seed=42)
        return {
            "train": split_1["train"],
            "validation": val_test["train"],
            "test": val_test["test"],
        }

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, job_id: int, dataset_name: str, hyperparams: dict) -> None:
        output_dir = os.path.join(settings.MODEL_DIR, str(job_id))
        os.makedirs(output_dir, exist_ok=True)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Fine-tuning job %d — device=%s, dataset=%s", job_id, device, dataset_name)

        tokenizer = _load_tokenizer(settings.FINBERT_MODEL)
        model = _load_model(settings.FINBERT_MODEL, num_labels=3).to(device)

        # Overwrite the inherited label map with the canonical one for
        # *this* dataset so model.config.id2label matches what the
        # logit indices actually mean after training. Without this
        # step save_model() would persist the base checkpoint's map
        # (e.g. FinBERT-tone's {0:Neutral,1:Positive,2:Negative}),
        # which silently mis-routes every prediction at inference
        # time. This is the root cause of the poisoned-labels bug
        # we hit on job 1.
        dataset_meta = next(
            (d for d in AVAILABLE_DATASETS if d["name"] == dataset_name), None
        )
        canonical = (dataset_meta or {}).get("canonical_labels")
        if canonical:
            id2label = {int(k): v for k, v in canonical.items()}
            label2id = {v: k for k, v in id2label.items()}
            model.config.id2label = id2label
            model.config.label2id = label2id
            logger.info("Set canonical label map for job %d: %s", job_id, id2label)
        else:
            logger.warning(
                "Dataset %s has no canonical_labels — model config will "
                "inherit the base checkpoint's id2label which is usually wrong",
                dataset_name,
            )

        raw_dataset = self.download_dataset(dataset_name)
        splits = self.prepare_dataset(raw_dataset, tokenizer)

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=hyperparams.get("epochs", 3),
            per_device_train_batch_size=hyperparams.get("batch_size", 16),
            per_device_eval_batch_size=hyperparams.get("batch_size", 16),
            learning_rate=hyperparams.get("learning_rate", 2e-5),
            weight_decay=hyperparams.get("weight_decay", 0.01),
            warmup_ratio=hyperparams.get("warmup_ratio", 0.1),
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            logging_steps=50,
            fp16=torch.cuda.is_available(),
            report_to="none",
        )

        callbacks = []
        if self._session:
            callbacks.append(_ProgressCallback(self._session, job_id))

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=splits["train"],
            eval_dataset=splits["validation"],
            processing_class=tokenizer,
            compute_metrics=_compute_metrics,
            callbacks=callbacks,
        )

        trainer.train()

        test_metrics = trainer.evaluate(splits["test"])
        final_metrics = {k: round(v, 6) for k, v in test_metrics.items() if isinstance(v, (int, float))}

        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        if self._session:
            job = self._session.query(FinetuningJob).filter_by(id=job_id).first()
            if job:
                job.status = "completed"
                job.model_path = output_dir
                job.completed_at = datetime.utcnow()
                job.metrics = {**(job.metrics or {}), **final_metrics}
                self._session.commit()

        logger.info("Fine-tuning job %d complete — metrics: %s", job_id, final_metrics)

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    @staticmethod
    def list_datasets() -> list[dict]:
        return [
            {"name": d["name"], "description": d["description"], "labels": d["labels"]}
            for d in AVAILABLE_DATASETS
        ]

    @staticmethod
    def list_models() -> list[dict]:
        models_dir = Path(settings.MODEL_DIR)
        if not models_dir.exists():
            return []
        results = []
        for entry in sorted(models_dir.iterdir()):
            if entry.is_dir() and (entry / "config.json").exists():
                results.append(
                    {
                        "job_id": entry.name,
                        "path": str(entry),
                        "size_mb": round(
                            sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) / 1_048_576,
                            2,
                        ),
                    }
                )
        return results
