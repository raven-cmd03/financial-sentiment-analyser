"""Bulk-index every ``news_articles`` row into ChromaDB.

The recurring ``index_vector_store_task`` only walks forward from a
``collected_date`` cursor stored in Redis, which means new deployments and
post-backfill catch-ups take forever (at 1000 articles per 30 min tick
the 5-year backfill corpus of ~350k rows would take a week to cover).
This script walks the same table in ascending ``collected_date`` order but
in a single process with a configurable batch size, and nudges the Redis
cursor forward as it goes so the recurring task picks up seamlessly once
the script finishes.

Typical invocations (run from inside the backend container)::

    # Full corpus, default 2000 per batch, resumes from stored cursor.
    docker compose exec backend python -m app.scripts.index_all_articles

    # Force a fresh pass from the beginning (e.g. after changing the
    # metadata schema) regardless of the stored cursor.
    docker compose exec backend python -m app.scripts.index_all_articles \\
        --reset-cursor

    # Narrow window, larger batches (works well on a warm GPU).
    docker compose exec backend python -m app.scripts.index_all_articles \\
        --since 2024-01-01 --batch-size 5000

Re-running is always safe: ``VectorStoreService.index_articles`` issues
``upsert`` calls, so any articles already in Chroma are overwritten with
the current schema rather than duplicated.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime

logger = logging.getLogger("index_all_articles")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill ChromaDB with every article in the DB.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2000,
        help="Articles per embedding batch (default: 2000).",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help=(
            "Only index articles with collected_date >= this ISO date "
            "(YYYY-MM-DD). Useful for partial backfills."
        ),
    )
    parser.add_argument(
        "--reset-cursor",
        action="store_true",
        help=(
            "Ignore the current Redis cursor and start from the earliest "
            "article (or --since if supplied). Does NOT delete Chroma — "
            "upsert makes the re-pass idempotent."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after indexing this many articles (default: no cap).",
    )
    return parser.parse_args()


def _parse_since(raw: str | None) -> datetime | None:
    if not raw:
        return None
    # Accept both ``YYYY-MM-DD`` and full ISO timestamps.
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise SystemExit(f"Could not parse --since value {raw!r}")


def _resolve_start_cursor(
    redis_client, reset: bool, since: datetime | None
) -> datetime | None:
    """Work out where to start the scan.

    Priority: ``--since`` > stored Redis cursor > beginning of table.
    ``--reset-cursor`` forces ignoring the stored value.
    """
    from app.workers.tasks import _INDEXER_CURSOR_KEY

    if since is not None:
        return since
    if reset:
        return None
    raw = redis_client.get(_INDEXER_CURSOR_KEY)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        logger.warning("Corrupt cursor %r in Redis; starting from the top", raw)
        return None


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    args = _parse_args()

    from app.database import SyncSessionLocal
    from app.models import NewsArticle
    from app.services.vector_store import VectorStoreService
    from app.workers.tasks import (
        _INDEXER_CURSOR_KEY,
        _articles_to_index_payload,
        _get_redis_sync,
        _load_tickers_for_articles,
    )

    since = _parse_since(args.since)
    redis_client = _get_redis_sync()
    cursor = _resolve_start_cursor(redis_client, args.reset_cursor, since)
    logger.info(
        "Starting bulk index (batch=%d, cursor=%s, limit=%s)",
        args.batch_size,
        cursor.isoformat() if cursor else "<none>",
        args.limit if args.limit else "unlimited",
    )

    # A total-count probe makes the progress log meaningful. It's a single
    # cheap COUNT(*) so the overhead is negligible.
    session = SyncSessionLocal()
    try:
        total_query = session.query(NewsArticle)
        if cursor is not None:
            total_query = total_query.filter(
                NewsArticle.collected_date > cursor
            )
        total = total_query.count()
        logger.info("Articles awaiting indexing: %d", total)

        vs = VectorStoreService()
        indexed = 0
        start = time.monotonic()
        while True:
            if args.limit and indexed >= args.limit:
                logger.info("Hit --limit %d; stopping.", args.limit)
                break

            batch_q = session.query(NewsArticle)
            if cursor is not None:
                batch_q = batch_q.filter(
                    NewsArticle.collected_date > cursor
                )
            batch = (
                batch_q.order_by(NewsArticle.collected_date.asc())
                .limit(args.batch_size)
                .all()
            )
            if not batch:
                break

            tickers_by_id = _load_tickers_for_articles(
                session, [a.article_id for a in batch]
            )
            payload = _articles_to_index_payload(batch, tickers_by_id)
            vs.index_articles(payload)

            # Advance the cursor to the newest ``collected_date`` we just
            # indexed and persist it; subsequent recurring task runs will
            # happily pick up from here.
            new_cursor = max(
                (a.collected_date for a in batch if a.collected_date),
                default=cursor,
            )
            cursor = new_cursor
            if cursor is not None:
                redis_client.set(_INDEXER_CURSOR_KEY, cursor.isoformat())

            indexed += len(batch)
            elapsed = time.monotonic() - start
            rate = indexed / elapsed if elapsed > 0 else 0
            eta = (total - indexed) / rate if rate > 0 else float("inf")
            logger.info(
                "  +%d (%d / ~%d, %.0f art/s, ETA %.0fs, cursor=%s)",
                len(batch),
                indexed,
                total,
                rate,
                eta,
                cursor.isoformat() if cursor else "<none>",
            )

        logger.info(
            "Done. Indexed %d article(s) in %.1fs.",
            indexed,
            time.monotonic() - start,
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
