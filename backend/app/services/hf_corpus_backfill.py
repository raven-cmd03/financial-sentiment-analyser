"""Bulk backfill from the ``Brianferrell787/financial-news-multisource``
HuggingFace dataset.

Why a separate service (not a provider inside ``backfill.py``):

* ``run_backfill`` is built around the assumption of ``(ticker, time-window)``
  API calls — the provider returns the articles for that window, we
  persist them, advance the cursor, repeat. The HF corpus doesn't
  work that way: we stream every row in a subset once and *filter*
  client-side by ticker set. Shoehorning that into the window loop
  would make the existing code harder to reason about and waste work
  (we'd re-scan the same Parquet for every ticker).
* The HF path has no rate limit, no API key beyond gated-dataset
  auth, and no per-ticker call budget — none of the knobs that exist
  in ``run_backfill``.

What this module reuses:

* ``_persist_articles_sync`` — same dedup-by-URL-hash path the GDELT
  and AV backfills use, so HF rows land in the same ``news_articles``
  shape as everything else.
* ``_chunks`` + ``_SENTIMENT_BATCH_SIZE`` — same Celery dispatch cadence.
* ``Company`` lookup — we backfill for every Company row matching the
  caller's ticker list (default: all companies in the DB).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence

from app.database import SyncSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class SubsetBackfillResult:
    subset: str
    rows_scanned: int = 0
    rows_matched: int = 0
    articles_new: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def as_dict(self) -> dict:
        elapsed = (self.finished_at or time.time()) - self.started_at
        return {
            "subset": self.subset,
            "rows_scanned": self.rows_scanned,
            "rows_matched": self.rows_matched,
            "articles_new": self.articles_new,
            "errors": list(self.errors),
            "elapsed_seconds": round(elapsed, 1),
        }


@dataclass
class HFBackfillSummary:
    subsets: list[SubsetBackfillResult] = field(default_factory=list)
    per_ticker_new: dict[str, int] = field(default_factory=dict)
    total_articles_queued_for_sentiment: int = 0

    def as_dict(self) -> dict:
        return {
            "total_rows_scanned": sum(s.rows_scanned for s in self.subsets),
            "total_rows_matched": sum(s.rows_matched for s in self.subsets),
            "total_articles_new": sum(s.articles_new for s in self.subsets),
            "total_articles_queued_for_sentiment": self.total_articles_queued_for_sentiment,
            "per_subset": [s.as_dict() for s in self.subsets],
            "per_ticker_new": dict(sorted(self.per_ticker_new.items())),
        }


def _iter_batches(it: Iterable[dict], size: int) -> Iterable[list[dict]]:
    batch: list[dict] = []
    for row in it:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def run_hf_corpus_backfill(
    *,
    tickers: Sequence[str] | None = None,
    subsets: Sequence[str] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    max_rows_per_subset: int | None = None,
    batch_size: int = 200,
    dispatch_sentiment: bool = True,
    progress_every: int = 50_000,
) -> HFBackfillSummary:
    """Populate ``news_articles`` from the HF financial-news corpus.

    Parameters
    ----------
    tickers
        Ticker symbols to match against ``extra_fields.stocks`` /
        ``mentioned_companies``. ``None`` → every Company row in the DB.
        Matching is case-insensitive and ignores the ``$`` prefix used
        for index tickers in ``sentarl_combined``.
    subsets
        Which ticker-tagged subsets to stream. ``None`` →
        ``TICKER_TAGGED_SUBSETS`` (all 4). Limiting to one or two is
        the right call if you want to spot-check the pipeline before
        the full multi-hour run.
    start_date, end_date
        Optional inclusive bounds on the article's publication date.
        Rows with unparseable dates fall through the filter (we keep
        them) so you don't lose data because of one bad ISO string.
    max_rows_per_subset
        Safety ceiling on how many rows we'll scan before giving up on
        a subset. Use it to time-box exploratory runs. ``None`` → no cap.
    batch_size
        How many matching articles to accumulate before a DB commit +
        sentiment dispatch. 200 is a sweet spot — the Celery task loads
        FinBERT once per batch and larger batches reduce queue chatter.
    dispatch_sentiment
        Enqueue ``analyze_sentiment_task`` after each batch persists.
        Turn off for dry runs / tests.
    progress_every
        Log a "scanned N rows, matched M" line every N rows per subset.
        Lower for tight feedback, higher for quiet bulk runs.

    Returns
    -------
    HFBackfillSummary
        Per-subset + per-ticker counts.
    """
    # Local imports: this module is imported from CLI scripts and must
    # not pull transformers/torch into that process.
    from app.clients import (
        HF_DATASET_REPO,
        TICKER_TAGGED_SUBSETS,
        HFCorpusClient,
        HFCorpusError,
    )
    from app.config import get_settings
    from app.models import ArticleCompany, Company, NewsArticle
    from app.services.backfill import (
        _SENTIMENT_BATCH_SIZE,
        _chunks,
        _persist_articles_sync,
    )

    settings = get_settings()
    if not settings.HUGGINGFACE_API_KEY:
        raise HFCorpusError(
            "HUGGINGFACE_API_KEY is empty. Set it in .env and accept the "
            f"dataset terms at https://huggingface.co/datasets/{HF_DATASET_REPO} "
            "before running this backfill."
        )

    chosen_subsets = tuple(subsets) if subsets else TICKER_TAGGED_SUBSETS
    summary = HFBackfillSummary()

    session = SyncSessionLocal()
    try:
        query = session.query(Company)
        if tickers:
            upper = [t.upper() for t in tickers]
            query = query.filter(Company.ticker_symbol.in_(upper))
        companies = query.all()

        if not companies:
            logger.warning(
                "No companies match tickers=%s; nothing to backfill", tickers
            )
            return summary

        # Build a ticker → Company map for O(1) lookup in the hot loop.
        ticker_to_company = {c.ticker_symbol.upper(): c for c in companies}
        ticker_set = set(ticker_to_company.keys())

        logger.info(
            "HF backfill: %d companies, %d subsets (%s), batch=%d",
            len(companies),
            len(chosen_subsets),
            ", ".join(chosen_subsets),
            batch_size,
        )

        client = HFCorpusClient(token=settings.HUGGINGFACE_API_KEY)
        all_new_ids: list[str] = []

        for subset in chosen_subsets:
            sub_result = SubsetBackfillResult(subset=subset)
            summary.subsets.append(sub_result)
            logger.info("Streaming subset '%s'…", subset)

            try:
                row_stream = _filter_rows(
                    client.stream_subset(subset),
                    ticker_set=ticker_set,
                    start_date=start_date,
                    end_date=end_date,
                    max_rows=max_rows_per_subset,
                    progress_every=progress_every,
                    sub_result=sub_result,
                )
                for batch in _iter_batches(row_stream, batch_size):
                    # Group by resolved Company so _persist_articles_sync
                    # can link to the right company_id. A single row can
                    # mention multiple of our tickers (e.g. Yahoo Finance
                    # articles with stocks=[AAPL,MSFT,GOOGL]), in which
                    # case we persist the article once per company — the
                    # unique article_id means the NewsArticle row is
                    # inserted on the first pass and subsequent passes
                    # just add the ArticleCompany link.
                    grouped: dict[str, list[dict]] = {}
                    for row in batch:
                        for tkr in row.get("tickers") or []:
                            if tkr in ticker_set:
                                grouped.setdefault(tkr, []).append(row)

                    for tkr, rows in grouped.items():
                        company = ticker_to_company[tkr]
                        try:
                            new_ids = _persist_articles_sync(
                                session,
                                company,
                                rows,
                                NewsArticle,
                                ArticleCompany,
                            )
                            session.commit()
                        except Exception as exc:
                            session.rollback()
                            logger.exception(
                                "Persist failed for %s in subset %s",
                                tkr,
                                subset,
                            )
                            sub_result.errors.append(
                                f"persist[{tkr}]: {exc}"
                            )
                            continue

                        if new_ids:
                            sub_result.articles_new += len(new_ids)
                            summary.per_ticker_new[tkr] = (
                                summary.per_ticker_new.get(tkr, 0) + len(new_ids)
                            )
                            all_new_ids.extend(new_ids)

            except HFCorpusError as exc:
                # Bubble up auth/network errors with the subset
                # annotation so operators see which one failed — don't
                # abort the whole run, the next subset might work.
                logger.error("Subset '%s' unavailable: %s", subset, exc)
                sub_result.errors.append(f"stream: {exc}")
            except Exception as exc:
                logger.exception("Unexpected error streaming subset '%s'", subset)
                sub_result.errors.append(f"stream: {exc}")
            finally:
                sub_result.finished_at = time.time()

            logger.info(
                "Subset '%s' done: scanned=%d matched=%d new=%d",
                subset,
                sub_result.rows_scanned,
                sub_result.rows_matched,
                sub_result.articles_new,
            )

        if dispatch_sentiment and all_new_ids:
            from app.workers.tasks import analyze_sentiment_task

            for batch in _chunks(all_new_ids, _SENTIMENT_BATCH_SIZE):
                analyze_sentiment_task.delay(batch)
                summary.total_articles_queued_for_sentiment += len(batch)

            logger.info(
                "Dispatched %d articles for FinBERT analysis in %d batch(es)",
                summary.total_articles_queued_for_sentiment,
                (len(all_new_ids) + _SENTIMENT_BATCH_SIZE - 1)
                // _SENTIMENT_BATCH_SIZE,
            )

        return summary
    finally:
        session.close()


def _filter_rows(
    stream: Iterable[dict],
    *,
    ticker_set: set[str],
    start_date: datetime | None,
    end_date: datetime | None,
    max_rows: int | None,
    progress_every: int,
    sub_result: SubsetBackfillResult,
) -> Iterable[dict]:
    """Filter the raw subset stream by ticker + date range.

    Yields only rows where at least one of ``row["tickers"]`` is in
    ``ticker_set``. Emits periodic progress updates on the sub-result
    counter so the caller gets heartbeats for multi-million-row subsets.
    """
    for row in stream:
        sub_result.rows_scanned += 1
        if max_rows is not None and sub_result.rows_scanned > max_rows:
            logger.info(
                "Subset '%s' hit max_rows cap (%d); stopping scan",
                sub_result.subset,
                max_rows,
            )
            break

        if sub_result.rows_scanned % progress_every == 0:
            logger.info(
                "  … '%s' scanned=%d matched=%d",
                sub_result.subset,
                sub_result.rows_scanned,
                sub_result.rows_matched,
            )

        row_tickers = set(row.get("tickers") or [])
        if not row_tickers & ticker_set:
            continue

        if start_date is not None or end_date is not None:
            if not _date_in_range(row.get("publication_date"), start_date, end_date):
                continue

        sub_result.rows_matched += 1
        yield row


def _date_in_range(
    pub_date: str | None,
    start: datetime | None,
    end: datetime | None,
) -> bool:
    """True if ``pub_date`` (ISO 8601 string) falls in ``[start, end]``.

    Unparseable / missing dates pass through — better to occasionally
    admit a date-missing row than drop silently. Both bounds are
    inclusive; ``None`` means unbounded on that side.
    """
    if not pub_date or not isinstance(pub_date, str):
        return True
    try:
        # Handle both "…Z" and "…+00:00" variants.
        parsed = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True
    # Normalise to naive UTC for comparison against the caller's args.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    if start is not None and parsed < start:
        return False
    if end is not None and parsed > end:
        return False
    return True
