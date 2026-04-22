"""Recalculate sentiment-price correlations on demand.

Usually driven by Celery beat on a schedule. This CLI lets you trigger
the same work manually after a backfill lands so you don't have to
wait for the next beat tick.

By default it runs *inline* in the backend container — you see the
per-ticker progress live and it finishes in seconds because
``compute_all_correlations`` is just pandas math on already-persisted
sentiment + price rows. If you'd rather queue it behind whatever
Celery is already doing, pass ``--dispatch`` to fire the existing
``update_correlations_task`` instead.

Usage (from inside the backend container)::

    # run for every tracked company, 30-day window (the default)
    docker compose exec backend python -m app.scripts.update_correlations

    # only a few tickers, 1-year window
    docker compose exec backend python -m app.scripts.update_correlations \\
        --tickers AAPL,MSFT,NVDA --days 365

    # fire-and-forget via Celery (ends up behind the sentiment queue)
    docker compose exec backend python -m app.scripts.update_correlations --dispatch

Correlation records are idempotent-ish: running twice overwrites the
previous day's pearson/spearman/lag values for each ticker, which is
exactly what we want after the backfills add new sentiment rows.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Iterable

logger = logging.getLogger("update_correlations")


def _parse_tickers(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    return parts or None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually trigger correlation recomputation.",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers to compute (default: every Company row).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Alignment window in days (default: 30). "
        "Use larger values once the 5-year backfill lands.",
    )
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="Enqueue update_correlations_task on Celery instead of running inline.",
    )
    return parser.parse_args()


def _resolve_tickers_sync(explicit: list[str] | None) -> list[str]:
    """Return the tickers to process. Falls back to every Company row
    when no --tickers flag is supplied."""
    from app.database import SyncSessionLocal
    from app.models import Company

    if explicit:
        return explicit

    session = SyncSessionLocal()
    try:
        return [row.ticker_symbol for row in session.query(Company).all()]
    finally:
        session.close()


async def _run_inline(tickers: Iterable[str], days: int) -> dict[str, int]:
    """Run ``compute_all_correlations`` for each ticker with one shared
    AsyncSession. Returns ``{ticker: rows_persisted}``; value is ``0``
    when the ticker didn't have enough aligned data.
    """
    from app.database import AsyncSessionLocal
    from app.services.correlation import CorrelationCalculator

    calc = CorrelationCalculator()
    results: dict[str, int] = {}

    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            try:
                rows = await calc.compute_all_correlations(ticker, db, days=days)
                results[ticker] = len(rows)
                logger.info(
                    "  %s: %d correlation record(s) written",
                    ticker,
                    len(rows),
                )
            except Exception as exc:
                # Never let one bad ticker stall the rest.
                logger.error("  %s: FAILED (%s)", ticker, exc)
                await db.rollback()
                results[ticker] = 0
        await db.commit()

    return results


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    args = _parse_args()

    explicit = _parse_tickers(args.tickers)

    if args.dispatch:
        # Delegate to the existing Celery task so the run survives
        # the shell exiting. We don't scope it to specific tickers —
        # the task processes every Company row by design.
        if explicit:
            logger.warning(
                "--dispatch ignores --tickers; the task covers every Company. "
                "Run inline if you want per-ticker scoping.",
            )
        from app.workers.tasks import update_correlations_task

        result = update_correlations_task.delay()
        logger.info(
            "Enqueued update_correlations_task (id=%s). Watch "
            "`docker compose logs -f celery-worker` for progress.",
            result.id,
        )
        return 0

    tickers = _resolve_tickers_sync(explicit)
    if not tickers:
        logger.error("No tickers resolved. Seed companies first.")
        return 1

    logger.info(
        "Computing correlations for %d ticker(s) with days=%d (inline)…",
        len(tickers),
        args.days,
    )
    results = asyncio.run(_run_inline(tickers, args.days))

    total_rows = sum(results.values())
    winners = sum(1 for v in results.values() if v > 0)
    skipped = [t for t, n in results.items() if n == 0]

    logger.info(
        "Done. %d/%d ticker(s) produced correlations (%d total rows).",
        winners,
        len(tickers),
        total_rows,
    )
    if skipped:
        logger.info(
            "No-data tickers (skipped, <5 aligned points): %s",
            ", ".join(skipped[:20]) + ("…" if len(skipped) > 20 else ""),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
