"""CLI entry point for the backtest trader-agent simulation.

Run from inside the backend container so it picks up the same DB /
Redis / Groq settings the rest of the stack uses::

    docker compose exec backend python -m app.scripts.run_simulation

Flags::

    --profiles day_trader,swing_trader,...   Limit to a subset (default: all)
    --tickers  AAPL,MSFT                     Override universe
    --start    YYYY-MM-DD                    Lower bound on dates
    --end      YYYY-MM-DD                    Upper bound on dates
    --async                                  Dispatch via Celery instead of
                                             running inline (useful if the run
                                             will take a long time)

Writes all artefacts under ``SIMULATION_OUTPUT_DIR/<run_id>/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from app.database import SyncSessionLocal
from app.models import SimulationRun
from app.services.simulation.profiles import TRADER_PROFILES


logger = logging.getLogger("run_simulation")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.run_simulation",
        description="Run the backtest trader-agent simulation.",
    )
    parser.add_argument("--profiles", default=None, help="Comma-separated profile names")
    parser.add_argument("--tickers", default=None, help="Comma-separated ticker override")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD lower bound")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD upper bound")
    parser.add_argument(
        "--async",
        dest="run_async",
        action="store_true",
        help="Dispatch via Celery instead of running inline.",
    )
    return parser.parse_args(argv)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise SystemExit(f"--start/--end must be YYYY-MM-DD, got: {value!r}")


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)

    profiles = _parse_csv(args.profiles)
    if profiles:
        unknown = [p for p in profiles if p not in TRADER_PROFILES]
        if unknown:
            logger.error("Unknown profile(s): %s. Known: %s", unknown, sorted(TRADER_PROFILES))
            return 2

    tickers = _parse_csv(args.tickers)
    start_date = _parse_date(args.start)
    end_date = _parse_date(args.end)

    # Create the run row first so the ID can be logged and the report path
    # becomes deterministic.
    session = SyncSessionLocal()
    try:
        run = SimulationRun(status="pending", universe=[], config={})
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.run_id
    finally:
        session.close()

    logger.info("Created SimulationRun id=%d", run_id)

    if args.run_async:
        from app.workers.tasks import run_simulation_task

        task = run_simulation_task.delay(
            run_id=run_id,
            profiles=profiles,
            universe=tickers,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )
        logger.info("Dispatched to Celery task_id=%s", task.id)
        print(json.dumps({"run_id": run_id, "task_id": task.id, "mode": "async"}, indent=2))
        return 0

    from app.services.simulation.engine import run_simulation as _run

    result = _run(
        run_id=run_id,
        profile_names=profiles,
        universe_override=tickers,
        start_date=start_date,
        end_date=end_date,
    )
    print(json.dumps(result, default=str, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
