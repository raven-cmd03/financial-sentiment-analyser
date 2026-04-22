import asyncio
import csv
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import require_api_key
from app.config import get_settings
from app.database import get_db
from app.models import FinetuningJob
from app.schemas.schemas import FinetuningJobCreate, FinetuningJobOut, DatasetInfo, ModelInfo
from app.services.finetuning import FineTuningPipeline
from app.workers.tasks import run_finetuning_task

logger = logging.getLogger(__name__)
settings = get_settings()

# Every route in this router requires the shared API key: fine-tuning is an
# expensive, destructive operation (writes datasets + spawns GPU jobs).
router = APIRouter(dependencies=[Depends(require_api_key)])


_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_dataset_filename(original_name: str) -> str:
    """Return a server-generated filename for a user-uploaded dataset.

    Always ignores the user-supplied directory component and unsafe chars.
    A UUID is appended so repeated uploads don't overwrite each other.
    """
    stem = Path(original_name).stem or "dataset"
    stem = _SAFE_STEM_RE.sub("_", stem)[:50] or "dataset"
    return f"{stem}-{uuid.uuid4().hex}.csv"


@router.get("/datasets", response_model=list[DatasetInfo])
async def list_datasets():
    built_in = FineTuningPipeline.list_datasets()

    datasets = []
    for d in built_in:
        datasets.append(DatasetInfo(
            name=d["name"],
            description=d["description"],
            sample_count=0,
            labels=d["labels"],
        ))

    custom_dir = Path(settings.DATASET_DIR)
    if custom_dir.exists():
        for csv_file in custom_dir.glob("*.csv"):
            try:
                with open(csv_file, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    row_count = sum(1 for _ in reader)
                datasets.append(DatasetInfo(
                    name=csv_file.stem,
                    description=f"Custom dataset ({csv_file.name})",
                    sample_count=row_count,
                    labels=header or [],
                ))
            except Exception:
                logger.warning("Could not read dataset file %s", csv_file)

    return datasets


@router.post("/datasets/upload", response_model=DatasetInfo)
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    # Read with a hard size cap to prevent unbounded memory / disk use.
    content = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_BYTES} bytes",
        )

    dest_dir = Path(settings.DATASET_DIR).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_dataset_filename(file.filename)
    dest_path = (dest_dir / safe_name).resolve()

    # Defence-in-depth: reject any resolved path that escapes the dataset dir.
    try:
        dest_path.relative_to(dest_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset filename")

    with open(dest_path, "wb") as f:
        f.write(content)

    try:
        lines = content.decode("utf-8", errors="replace").splitlines()
        reader = csv.reader(lines)
        header = next(reader, [])
        row_count = sum(1 for _ in reader)
    except Exception:
        logger.exception("Failed to parse uploaded CSV %s", safe_name)
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Could not parse CSV contents")

    return DatasetInfo(
        name=Path(safe_name).stem,
        description=f"Custom dataset (uploaded as {safe_name})",
        sample_count=row_count,
        labels=header,
    )


@router.post("/jobs", response_model=FinetuningJobOut, status_code=201)
async def create_job(
    body: FinetuningJobCreate,
    db: AsyncSession = Depends(get_db),
):
    job = FinetuningJob(
        dataset_name=body.dataset_name,
        hyperparams=body.hyperparams,
        status="pending",
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    run_finetuning_task.delay(job.id)

    return job


@router.get("/jobs", response_model=list[FinetuningJobOut])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FinetuningJob).order_by(desc(FinetuningJob.created_at))
    )
    return result.scalars().all()


@router.get("/jobs/{job_id}", response_model=FinetuningJobOut)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(FinetuningJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Fine-tuning job not found")
    return job


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await db.get(FinetuningJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Fine-tuning job not found")

    async def event_generator():
        while True:
            await db.refresh(job)
            yield {
                "event": "progress",
                "data": FinetuningJobOut.model_validate(job).model_dump_json(),
            }
            if job.status in ("completed", "failed"):
                yield {"event": "done", "data": job.status}
                break
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


@router.get("/models", response_model=list[ModelInfo])
async def list_models(db: AsyncSession = Depends(get_db)):
    models: list[ModelInfo] = [
        ModelInfo(
            id="base-finbert",
            name="ProsusAI/FinBERT (base)",
            is_active=True,
            accuracy=None,
            source="base",
        )
    ]

    result = await db.execute(
        select(FinetuningJob)
        .where(FinetuningJob.status == "completed", FinetuningJob.model_path.isnot(None))
        .order_by(desc(FinetuningJob.completed_at))
    )
    jobs = result.scalars().all()

    has_active = any(j.is_active == 1 for j in jobs)
    if has_active:
        models[0].is_active = False

    for j in jobs:
        metrics = j.metrics or {}
        models.append(ModelInfo(
            id=f"ft-{j.id}",
            name=f"FinBERT fine-tuned (job {j.id} — {j.dataset_name})",
            is_active=j.is_active == 1,
            accuracy=metrics.get("eval_accuracy") or metrics.get("accuracy"),
            source="finetuned",
        ))

    return models


@router.post("/models/{model_id}/activate", response_model=ModelInfo)
async def activate_model(model_id: str, db: AsyncSession = Depends(get_db)):
    if model_id == "base-finbert":
        await db.execute(
            select(FinetuningJob)  # reset all
        )
        result = await db.execute(select(FinetuningJob))
        for job in result.scalars().all():
            job.is_active = 0
        await db.flush()
        return ModelInfo(
            id="base-finbert",
            name="ProsusAI/FinBERT (base)",
            is_active=True,
            accuracy=None,
            source="base",
        )

    if not model_id.startswith("ft-"):
        raise HTTPException(status_code=400, detail="Invalid model ID")

    try:
        job_id = int(model_id.removeprefix("ft-"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")

    target_job = await db.get(FinetuningJob, job_id)
    if not target_job or target_job.status != "completed":
        raise HTTPException(status_code=404, detail="Fine-tuned model not found")

    all_jobs_result = await db.execute(select(FinetuningJob))
    for job in all_jobs_result.scalars().all():
        job.is_active = 1 if job.id == job_id else 0
    await db.flush()

    metrics = target_job.metrics or {}
    return ModelInfo(
        id=model_id,
        name=f"FinBERT fine-tuned (job {target_job.id} — {target_job.dataset_name})",
        is_active=True,
        accuracy=metrics.get("eval_accuracy") or metrics.get("accuracy"),
        source="finetuned",
    )
