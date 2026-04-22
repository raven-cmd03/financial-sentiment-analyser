"""Dispatch FinBERT analysis for articles that don't have a sentiment
result yet.

Why this exists: both ``run_backfill`` (GDELT / Alpha Vantage) and
``run_hf_corpus_backfill`` (HuggingFace corpus) only dispatch
``analyze_sentiment_task`` at the *end* of their run, so if a backfill
is aborted mid-flight the persisted articles can sit in
``news_articles`` without a matching ``sentiment_results`` row forever.
This script finds those orphans with a ``LEFT JOIN`` and enqueues them
in ``_SENTIMENT_BATCH_SIZE``-sized chunks for the worker to pick up.

Usage (from inside the backend container)::

    # dispatch every orphan
    python -m app.scripts.analyze_missing_sentiment

    # dry run — show how many orphans exist, don't enqueue anything
    python -m app.scripts.analyze_missing_sentiment --dry-run

    # cap total articles dispatched (useful for a first probe)
    python -m app.scripts.analyze_missing_sentiment --limit 1000

The script is idempotent: ``analyze_sentiment_task`` already skips any
article that already has a ``SentimentResult`` row, so re-running after
a partial processing pass is safe.
"""

from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger("analyze_missing_sentiment")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enqueue FinBERT analysis for articles missing a sentiment row.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Articles per analyze_sentiment_task Celery job (default: 100).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the total articles dispatched (default: dispatch all).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts, skip task dispatch.",
    )
    return parser.parse_args()


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    args = _parse_args()

    if args.batch_size <= 0:
        logger.error("--batch-size must be positive")
        return 1

    from app.database import SyncSessionLocal
    from app.models import NewsArticle, SentimentResult

    session = SyncSessionLocal()
    try:
        # LEFT OUTER JOIN — articles without a matching sentiment row.
        # Ordered by oldest first so a partial run still makes monotonic
        # progress against the backlog.
        query = (
            session.query(NewsArticle.article_id)
            .outerjoin(
                SentimentResult,
                SentimentResult.article_id == NewsArticle.article_id,
            )
            .filter(SentimentResult.article_id.is_(None))
            .order_by(NewsArticle.collected_date.asc())
        )
        if args.limit:
            query = query.limit(args.limit)

        article_ids = [row[0] for row in query.all()]
    finally:
        session.close()

    if not article_ids:
        logger.info("No articles without sentiment — nothing to dispatch.")
        return 0

    n_batches = (len(article_ids) + args.batch_size - 1) // args.batch_size
    logger.info(
        "Found %d article(s) missing sentiment. %s in %d batch(es) of size %d.",
        len(article_ids),
        "Would dispatch" if args.dry_run else "Dispatching",
        n_batches,
        args.batch_size,
    )

    if args.dry_run:
        return 0

    # Import here so --dry-run doesn't need a live Celery broker.
    from app.workers.tasks import analyze_sentiment_task

    dispatched = 0
    progress_step = max(args.batch_size * 10, 1)
    for batch in _chunks(article_ids, args.batch_size):
        analyze_sentiment_task.delay(batch)
        dispatched += len(batch)
        if dispatched % progress_step < args.batch_size:
            logger.info("… dispatched %d / %d", dispatched, len(article_ids))

    logger.info(
        "Dispatched %d article(s) across %d batch(es). "
        "Monitor progress via `docker compose logs -f celery-worker` "
        "or by polling the ``sentiment_results`` table.",
        dispatched,
        n_batches,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
