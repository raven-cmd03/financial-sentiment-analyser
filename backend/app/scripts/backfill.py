"""CLI entry point for the historical backfill.

Run from inside the backend container so it picks up the same DB /
Redis / Alpha Vantage settings the rest of the stack uses::

    docker compose exec backend python -m app.scripts.backfill --years 5

Flags::

    --tickers AAPL,MSFT   Only backfill these symbols (default: every
                          Company row in the DB)
    --years 5             Lookback window (default 5)
    --news-only           Skip price backfill
    --prices-only         Skip news backfill
    --news-provider NAME  gdelt (default — free, no API key, 5+ yrs),
                          alpha_vantage, or both
    --window-days 30      Per-call window size (days)
    --max-news-requests N Cap on news calls per ticker (default 200;
                          pass 0 to disable)
    --async               Dispatch via Celery instead of running inline
                          (useful if the backfill will take hours and
                          you don't want to hold the shell)
    --no-sentiment        Persist articles but don't queue FinBERT

Exit codes: ``0`` on success even if some tickers hit rate-limits;
``1`` only on hard failure (no companies, DB error, etc).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logger = logging.getLogger("backfill")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.backfill",
        description="Populate the DB with up to N years of news + prices.",
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated ticker symbols. Default: every Company row.",
        default=None,
    )
    parser.add_argument(
        "--years",
        type=int,
        default=5,
        help="Lookback window in years (default: 5)",
    )
    parser.add_argument(
        "--news-only",
        action="store_true",
        help="Skip price backfill.",
    )
    parser.add_argument(
        "--prices-only",
        action="store_true",
        help="Skip news backfill.",
    )
    parser.add_argument(
        "--news-provider",
        choices=("gdelt", "alpha_vantage", "both"),
        default="gdelt",
        help=(
            "Historical news source. 'gdelt' (default): free, no API "
            "key required, 5+ years of metadata. 'alpha_vantage': richer "
            "summaries but 25/day on free tier. 'both': GDELT first, "
            "then AV as a supplement (URL-hash dedup)."
        ),
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=30,
        help="Per-call window size in days (default: 30).",
    )
    parser.add_argument(
        "--max-news-requests",
        type=int,
        default=200,
        help=(
            "Cap on AV news calls per ticker to protect free-tier "
            "quotas. Pass 0 for no cap (default: 200)."
        ),
    )
    parser.add_argument(
        "--async",
        dest="async_dispatch",
        action="store_true",
        help="Dispatch via Celery instead of running inline.",
    )
    parser.add_argument(
        "--no-sentiment",
        action="store_true",
        help="Persist articles but don't queue FinBERT analysis.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    args = _parse_args(argv)

    if args.news_only and args.prices_only:
        logger.error("--news-only and --prices-only are mutually exclusive")
        return 1

    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if not tickers:
            logger.error("--tickers was empty after parsing")
            return 1

    max_req = None if args.max_news_requests == 0 else args.max_news_requests

    kwargs = {
        "tickers": tickers,
        "years_back": args.years,
        "include_news": not args.prices_only,
        "include_prices": not args.news_only,
        "news_window_days": args.window_days,
        "max_news_requests": max_req,
        "news_provider": args.news_provider,
    }

    if args.async_dispatch:
        from app.workers.tasks import backfill_historical_data_task

        async_kwargs = dict(kwargs)
        # Celery dispatch path doesn't take dispatch_sentiment; the task
        # always enqueues sentiment unless we add a kwarg there.
        task = backfill_historical_data_task.delay(**async_kwargs)
        print(
            json.dumps(
                {
                    "dispatched": True,
                    "task_id": task.id,
                    "params": {**async_kwargs, "tickers": tickers or "ALL"},
                },
                indent=2,
            )
        )
        return 0

    from app.services.backfill import run_backfill_sync

    try:
        summary = run_backfill_sync(
            **kwargs, dispatch_sentiment=not args.no_sentiment
        )
    except Exception:
        logger.exception("Backfill failed")
        return 1

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI shim
    sys.exit(main())
