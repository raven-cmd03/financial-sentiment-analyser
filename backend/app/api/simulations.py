"""Internal, API-key-gated endpoints for the backtest simulation.

Used for operator-side validation of the sentiment tool. No UI consumes
these — they exist so the simulation can be queued and inspected without
shelling into the worker container.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.database import get_db
from app.models import SimulationRun
from app.services.simulation.profiles import TRADER_PROFILES
from app.workers.tasks import run_simulation_task


logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])


class RunRequest(BaseModel):
    profiles: list[str] | None = Field(
        default=None,
        description="Subset of trader profile names. None = all registered profiles.",
    )
    tickers: list[str] | None = Field(
        default=None,
        description="Universe override. None = all tickers with both market + sentiment data.",
    )
    start_date: date | None = None
    end_date: date | None = None


class RunResponse(BaseModel):
    run_id: int
    task_id: str | None
    status: str


class RunStatusResponse(BaseModel):
    run_id: int
    status: str
    start_date: date | None
    end_date: date | None
    universe: list[str]
    report_path: str | None
    final_metrics: dict | None
    error: str | None
    created_at: str | None


@router.post("/run", response_model=RunResponse, status_code=202)
async def queue_simulation(
    body: RunRequest = Body(default_factory=RunRequest),
    db: AsyncSession = Depends(get_db),
):
    if body.profiles:
        unknown = [p for p in body.profiles if p not in TRADER_PROFILES]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown profile(s): {unknown}. "
                f"Known: {sorted(TRADER_PROFILES)}",
            )

    run = SimulationRun(status="pending", universe=[], config={})
    db.add(run)
    await db.flush()
    await db.refresh(run)

    task = run_simulation_task.delay(
        run_id=run.run_id,
        profiles=body.profiles,
        universe=body.tickers,
        start_date=body.start_date.isoformat() if body.start_date else None,
        end_date=body.end_date.isoformat() if body.end_date else None,
    )
    logger.info(
        "Queued simulation run_id=%d task_id=%s profiles=%s",
        run.run_id,
        task.id,
        body.profiles,
    )
    return RunResponse(run_id=run.run_id, task_id=task.id, status="queued")


@router.get("/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(SimulationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return RunStatusResponse(
        run_id=run.run_id,
        status=run.status,
        start_date=run.start_date,
        end_date=run.end_date,
        universe=list(run.universe or []),
        report_path=run.report_path,
        final_metrics=run.final_metrics or {},
        error=run.error,
        created_at=run.created_at.isoformat() if run.created_at else None,
    )


@router.get("/", response_model=list[RunStatusResponse])
async def list_runs(limit: int = 25, db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(SimulationRun).order_by(desc(SimulationRun.run_id)).limit(limit)
    )
    runs = result.scalars().all()
    return [
        RunStatusResponse(
            run_id=r.run_id,
            status=r.status,
            start_date=r.start_date,
            end_date=r.end_date,
            universe=list(r.universe or []),
            report_path=r.report_path,
            final_metrics=r.final_metrics or {},
            error=r.error,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in runs
    ]
