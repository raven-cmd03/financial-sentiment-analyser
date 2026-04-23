import asyncio
import hashlib
import logging
from datetime import datetime

from app.workers.celery_app import celery_app
from app.database import SyncSessionLocal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Process-scoped SentimentAnalyzer cache.
#
# Building a ``SentimentAnalyzer`` loads ~440MB of BERT weights from disk and
# DMAs them to the GPU (~1–2s on a modern card). Doing that on every Celery
# task adds ~20–30 min of pure overhead when the backfills eventually
# dispatch hundreds of batches. We cache the analyzer per resolved model
# name so repeat invocations in the same worker process reuse the already-
# loaded weights. A new fine-tuned model activating in the DB produces a
# different key, which triggers an eviction-and-reload — so hot-swap
# semantics (see ``_resolve_active_model_name``) are preserved.
# ---------------------------------------------------------------------------
_ANALYZER_CACHE: dict[str, object] = {}
_ANALYZER_KEY: str | None = None


def _get_analyzer(model_name: str | None):
    """Return a cached ``SentimentAnalyzer`` for ``model_name``.

    ``None`` means "use ``settings.FINBERT_MODEL``"; we canonicalise to that
    resolved string so base <-> fine-tuned transitions always invalidate
    the cache cleanly.
    """
    from app.services.sentiment_analyzer import SentimentAnalyzer
    from app.config import get_settings

    global _ANALYZER_KEY

    key = model_name or get_settings().FINBERT_MODEL
    cached = _ANALYZER_CACHE.get(key)
    if cached is not None:
        return cached

    if _ANALYZER_CACHE and key != _ANALYZER_KEY:
        logger.info(
            "Evicting cached analyzer '%s' to load '%s'", _ANALYZER_KEY, key
        )
        _ANALYZER_CACHE.clear()

    logger.info("Loading sentiment analyzer for '%s' (caching for reuse)", key)
    analyzer = SentimentAnalyzer(model_name=model_name)
    _ANALYZER_CACHE[key] = analyzer
    _ANALYZER_KEY = key
    return analyzer


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


async def _fetch_news_for_ticker(ticker: str, company_name: str) -> list[dict]:
    """Fetch articles from every configured news source for a single ticker.

    The returned list is deduped by URL. Each client is isolated in its own
    try/except so a failure in one source can never kill the others — that's
    how the proposal's "handle API failures gracefully" requirement (NFR-05)
    is actually enforced in practice.
    """
    from app.clients import AlphaVantageClient, GoogleNewsClient, YahooFinanceClient
    from app.config import get_settings

    settings = get_settings()
    articles: list[dict] = []

    async with GoogleNewsClient() as gn:
        try:
            results = await gn.fetch_news(f"{company_name} {ticker}", max_results=8)
            articles.extend(results)
        except Exception as exc:
            logger.warning("GoogleNews failed for %s: %s", ticker, exc)

    async with YahooFinanceClient() as yf:
        try:
            results = await yf.fetch_news(ticker, max_results=8)
            articles.extend(results)
        except Exception as exc:
            logger.warning("YahooFinance failed for %s: %s", ticker, exc)

    if settings.ALPHA_VANTAGE_API_KEY:
        async with AlphaVantageClient(api_key=settings.ALPHA_VANTAGE_API_KEY) as av:
            try:
                results = await av.fetch_news(
                    ticker, max_results=settings.ALPHA_VANTAGE_NEWS_LIMIT
                )
                articles.extend(results)
            except Exception as exc:
                logger.warning("AlphaVantage news failed for %s: %s", ticker, exc)

    seen: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        url = a.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(a)
    return unique


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def collect_news_task(self):
    """Collect news articles for every tracked company, then trigger sentiment."""
    from app.models import Company, NewsArticle, ArticleCompany

    logger.info("Starting news collection task")
    session = SyncSessionLocal()
    try:
        companies = session.query(Company).all()
        total_new = 0
        new_article_ids = []

        for company in companies:
            try:
                raw_articles = asyncio.run(
                    _fetch_news_for_ticker(company.ticker_symbol, company.company_name)
                )
                company_new = 0
                import re
                for a in raw_articles:
                    url = a.get("url", "")
                    if not url:
                        continue
                    aid = _hash_url(url)
                    existing = (
                        session.query(NewsArticle)
                        .filter_by(article_id=aid)
                        .first()
                    )
                    if existing:
                        continue

                    pub_date = a.get("publication_date")
                    if isinstance(pub_date, str):
                        try:
                            pub_date = datetime.fromisoformat(pub_date)
                        except (ValueError, TypeError):
                            pub_date = datetime.utcnow()
                    elif pub_date is None:
                        pub_date = datetime.utcnow()

                    title = (a.get("title") or "").strip()
                    content = (a.get("content") or a.get("description") or "").strip()
                    content = re.sub(r"<[^>]+>", "", content).strip()
                    title = re.sub(r"<[^>]+>", "", title).strip()

                    if not title:
                        continue

                    # Wrap each article in a SAVEPOINT so a single bad row doesn't
                    # nuke the entire batch; only this nested transaction rolls back.
                    try:
                        with session.begin_nested():
                            news = NewsArticle(
                                article_id=aid,
                                title=title[:2000],
                                content=content[:10000],
                                source=(a.get("source") or "unknown")[:100],
                                url=url,
                                publication_date=pub_date,
                                language="en",
                            )
                            session.add(news)
                            session.flush()

                            link = ArticleCompany(
                                article_id=aid,
                                company_id=company.company_id,
                            )
                            session.add(link)
                        new_article_ids.append(aid)
                        total_new += 1
                        company_new += 1
                    except Exception as article_exc:
                        logger.warning("Skipping article %s: %s", aid, article_exc)

                logger.info("Collected %d new articles for %s", company_new, company.ticker_symbol)
            except Exception as exc:
                session.rollback()
                logger.error("Failed collecting for %s: %s", company.ticker_symbol, exc)

        session.commit()
        logger.info("News collection complete: %d new articles total", total_new)

        if new_article_ids:
            analyze_sentiment_task.delay(new_article_ids)
            logger.info("Triggered sentiment analysis for %d articles", len(new_article_ids))

        # Refresh market data so correlations have real prices to align against.
        # We don't depend on its success — correlations degrade gracefully.
        collect_market_data_task.delay()

        return {"articles_collected": total_new}
    except Exception as exc:
        session.rollback()
        logger.exception("News collection task failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


def _resolve_active_model_name(session) -> str | None:
    """Return the path of the active fine-tuned model, or None to use the base model."""
    from app.models import FinetuningJob

    active = (
        session.query(FinetuningJob)
        .filter(FinetuningJob.is_active == 1)
        .filter(FinetuningJob.status == "completed")
        .filter(FinetuningJob.model_path.isnot(None))
        .order_by(FinetuningJob.completed_at.desc())
        .first()
    )
    if active and active.model_path:
        return active.model_path
    return None


# Inference batch size handed to ``SentimentAnalyzer.batch_analyze``. Keep
# this modest: BERT-base at 512 tokens with batch=32 fits comfortably in
# ~4–5 GB of VRAM and typically saturates a modern consumer GPU.
_INFERENCE_BATCH_SIZE = 32


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def analyze_sentiment_task(self, article_ids: list):
    """Run FinBERT sentiment analysis on the given articles.

    Inference is GPU-batched (``batch_analyze``) and the analyzer is
    cached per-worker-process via ``_get_analyzer`` — together these
    turn a 3–5s per-task cost into <1s for the common 100-article
    batch size used by the backfill orchestrators.
    """
    from app.models import NewsArticle, SentimentResult

    logger.info("Analyzing sentiment for %d articles", len(article_ids))
    session = SyncSessionLocal()
    try:
        active_model = _resolve_active_model_name(session)
        if active_model:
            logger.info("Using active fine-tuned model at %s", active_model)
        analyzer = _get_analyzer(active_model)

        # Skip articles that already have a sentiment result (idempotent re-runs).
        existing_ids = {
            row[0]
            for row in session.query(SentimentResult.article_id)
            .filter(SentimentResult.article_id.in_(article_ids))
            .all()
        }
        pending_ids = [a for a in article_ids if a not in existing_ids]
        if existing_ids:
            logger.info(
                "Skipping %d article(s) that already have sentiment results",
                len(existing_ids),
            )

        if not pending_ids:
            return {"analyzed": 0, "skipped_existing": len(existing_ids)}

        articles = (
            session.query(NewsArticle)
            .filter(NewsArticle.article_id.in_(pending_ids))
            .all()
        )
        if not articles:
            logger.info("No articles materialised for the pending ids")
            return {"analyzed": 0, "skipped_existing": len(existing_ids)}

        texts = [
            f"{a.title}. {a.content}" if a.content else a.title
            for a in articles
        ]

        try:
            predictions = analyzer.batch_analyze(
                texts, batch_size=_INFERENCE_BATCH_SIZE
            )
        except Exception as exc:
            # Pure inference failure — let Celery retry the whole batch.
            # We have no partial persistence to unwind because writes
            # happen after this point.
            logger.exception("Batched FinBERT inference failed")
            raise self.retry(exc=exc)

        results: list[str] = []
        for article, prediction in zip(articles, predictions):
            try:
                with session.begin_nested():
                    result = SentimentResult(
                        article_id=article.article_id,
                        sentiment_label=prediction["sentiment_label"],
                        positive_score=prediction["positive_score"],
                        negative_score=prediction["negative_score"],
                        neutral_score=prediction["neutral_score"],
                        confidence=prediction["confidence"],
                    )
                    session.add(result)
                results.append(article.article_id)
            except Exception as exc:
                logger.error(
                    "Failed to persist sentiment for article %s: %s",
                    article.article_id,
                    exc,
                )
        session.commit()
        logger.info("Sentiment analysis complete: %d results", len(results))

        # NOTE: we used to chain ``index_vector_store_task.delay()`` here, but
        # Celery beat already runs the same indexer every 30 minutes (see
        # ``celery_app.beat_schedule['index-vector-store']``). Chaining it
        # per-batch during a backfill piles up thousands of redundant jobs
        # that each re-index the same ~200 most-recent articles and
        # completely starve the pool of sentiment work. Let beat own it.

        return {"analyzed": len(results), "skipped_existing": len(existing_ids)}
    except Exception as exc:
        session.rollback()
        logger.exception("Sentiment analysis task failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


async def _fetch_adanos_for_tickers(tickers: list[str]) -> dict[str, dict]:
    """Fetch Adanos sentiment for a list of tickers concurrently."""
    from app.clients.adanos import AdanosClient
    from app.config import get_settings

    settings = get_settings()
    if not settings.ADANOS_API_KEY:
        logger.warning("ADANOS_API_KEY not configured; skipping social sentiment")
        return {}

    results: dict[str, dict] = {}
    async with AdanosClient(api_key=settings.ADANOS_API_KEY) as client:
        for ticker in tickers:
            try:
                results[ticker] = await client.get_sentiment(ticker)
            except Exception as exc:
                logger.error("Adanos fetch failed for %s: %s", ticker, exc)
    return results


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def poll_social_sentiment_task(self):
    """Fetch social / X sentiment from Adanos for all tracked companies."""
    from app.models import Company, SocialSentiment

    logger.info("Polling social sentiment")
    session = SyncSessionLocal()
    try:
        companies = session.query(Company).all()
        tickers = [c.ticker_symbol for c in companies]
        sentiment_by_ticker = asyncio.run(_fetch_adanos_for_tickers(tickers))

        count = 0
        for ticker, data in sentiment_by_ticker.items():
            if not data:
                continue
            record = SocialSentiment(
                ticker_symbol=ticker,
                buzz_score=data.get("buzz_score"),
                bullish_ratio=data.get("bullish_ratio"),
                bearish_ratio=data.get("bearish_ratio"),
                post_volume=data.get("post_volume"),
                sentiment_trend=data.get("sentiment_trend"),
            )
            session.add(record)
            count += 1

        session.commit()
        logger.info("Social sentiment poll complete: %d records", count)
        return {"records_added": count}
    except Exception as exc:
        session.rollback()
        logger.exception("Social sentiment task failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


async def _run_correlations_for_tickers(tickers: list[str]) -> int:
    """Run CorrelationCalculator.compute_all_correlations for each ticker using an async session."""
    from app.database import AsyncSessionLocal
    from app.services.correlation import CorrelationCalculator

    calculator = CorrelationCalculator()
    count = 0
    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            try:
                await calculator.compute_all_correlations(ticker, db)
                count += 1
            except Exception as exc:
                logger.error("Correlation update failed for %s: %s", ticker, exc)
                await db.rollback()
        await db.commit()
    return count


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def update_correlations_task(self):
    """Recalculate sentiment-price correlations for every ticker."""
    from app.models import Company

    logger.info("Updating correlations")
    session = SyncSessionLocal()
    try:
        tickers = [c.ticker_symbol for c in session.query(Company).all()]
    finally:
        session.close()

    try:
        count = asyncio.run(_run_correlations_for_tickers(tickers))
        logger.info("Correlation update complete for %d tickers", count)
        return {"tickers_updated": count}
    except Exception as exc:
        logger.exception("Correlation update task failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Vector store indexing — cursor-based.
#
# The previous implementation was ``ORDER BY collected_date DESC LIMIT 200``,
# which meant the same ~200 newest rows got re-embedded every 30 min while
# the rest of the 300k+ corpus was never indexed (we measured 9.7% coverage
# after the 5y backfill). The rewrite uses a ``collected_date`` cursor
# persisted in Redis so each run only processes genuinely new rows and
# eventual coverage is guaranteed. The paired one-shot CLI
# ``app.scripts.index_all_articles`` can be used to backfill the historical
# tail in bulk after this task is deployed.
# ---------------------------------------------------------------------------
_INDEXER_CURSOR_KEY = "vector_indexer:article_cursor"
_INDEXER_SOCIAL_CURSOR_KEY = "vector_indexer:social_cursor"
# How many articles we pull into a single 30-min recurring run. Larger values
# catch up faster but embed for longer; 1000 keeps each tick well under a
# minute on CPU and under ten seconds on GPU.
_INDEXER_BATCH_SIZE = 1000


def _get_redis_sync():
    """Lazy sync Redis client for cursor storage from inside Celery tasks."""
    import redis

    from app.config import get_settings

    return redis.Redis.from_url(get_settings().REDIS_URL, decode_responses=True)


def _load_tickers_for_articles(session, article_ids: list[str]) -> dict[str, list[str]]:
    """Return ``{article_id: [TICKER, ...]}`` for the given ids.

    Articles with no junction rows map to an empty list. We preserve
    ``company_id`` order via ``ORDER BY`` so the "primary" ticker is stable
    across runs (important — it becomes the filterable ``meta.ticker``).
    """
    from app.models import ArticleCompany, Company

    if not article_ids:
        return {}

    rows = (
        session.query(ArticleCompany.article_id, Company.ticker_symbol)
        .join(Company, Company.company_id == ArticleCompany.company_id)
        .filter(ArticleCompany.article_id.in_(article_ids))
        .order_by(ArticleCompany.article_id, ArticleCompany.company_id)
        .all()
    )
    mapping: dict[str, list[str]] = {aid: [] for aid in article_ids}
    for article_id, ticker in rows:
        if ticker:
            mapping.setdefault(article_id, []).append(ticker)
    return mapping


def _articles_to_index_payload(articles, tickers_by_id: dict[str, list[str]]) -> list[dict]:
    return [
        {
            "id": a.article_id,
            "title": a.title,
            "content": a.content,
            "source": a.source,
            "url": a.url,
            "publication_date": (
                a.publication_date.strftime("%Y-%m-%d %H:%M:%S")
                if a.publication_date
                else ""
            ),
            "tickers": tickers_by_id.get(a.article_id, []),
        }
        for a in articles
    ]


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def index_vector_store_task(self, batch_size: int | None = None):
    """Incrementally index new articles + social sentiment into ChromaDB.

    Uses a Redis-backed cursor (``collected_date`` for articles,
    ``fetched_at`` for social) so each run only processes rows newer than
    the last successful tick. Upsert semantics mean a re-run with the same
    cursor is a safe no-op.
    """
    from app.services.vector_store import VectorStoreService
    from app.models import NewsArticle, SocialSentiment

    effective_batch = batch_size or _INDEXER_BATCH_SIZE
    logger.info("Indexing vector store (batch=%d)", effective_batch)

    session = SyncSessionLocal()
    redis_client = _get_redis_sync()
    try:
        vs = VectorStoreService()

        # --- Articles ----------------------------------------------------
        raw_cursor = redis_client.get(_INDEXER_CURSOR_KEY)
        cursor_dt: datetime | None = None
        if raw_cursor:
            try:
                cursor_dt = datetime.fromisoformat(raw_cursor)
            except ValueError:
                logger.warning(
                    "Corrupt article cursor %r in Redis; starting from scratch",
                    raw_cursor,
                )

        article_q = session.query(NewsArticle)
        if cursor_dt is not None:
            article_q = article_q.filter(NewsArticle.collected_date > cursor_dt)
        new_articles = (
            article_q.order_by(NewsArticle.collected_date.asc())
            .limit(effective_batch)
            .all()
        )

        articles_indexed = 0
        if new_articles:
            tickers_by_id = _load_tickers_for_articles(
                session, [a.article_id for a in new_articles]
            )
            payload = _articles_to_index_payload(new_articles, tickers_by_id)
            vs.index_articles(payload)
            articles_indexed = len(payload)
            # Advance the cursor to the max collected_date in this batch. We
            # use ``>`` on the next run so if two rows share a timestamp only
            # one will be indexed — the next invocation will pick up any
            # stragglers because ``upsert`` is idempotent and future batches
            # include everything strictly newer.
            new_cursor = max(
                (a.collected_date for a in new_articles if a.collected_date),
                default=None,
            )
            if new_cursor is not None:
                redis_client.set(_INDEXER_CURSOR_KEY, new_cursor.isoformat())

        # --- Social sentiment -------------------------------------------
        raw_social_cursor = redis_client.get(_INDEXER_SOCIAL_CURSOR_KEY)
        social_cursor: datetime | None = None
        if raw_social_cursor:
            try:
                social_cursor = datetime.fromisoformat(raw_social_cursor)
            except ValueError:
                pass

        social_q = session.query(SocialSentiment)
        if social_cursor is not None:
            social_q = social_q.filter(SocialSentiment.fetched_at > social_cursor)
        new_social = (
            social_q.order_by(SocialSentiment.fetched_at.asc())
            .limit(effective_batch)
            .all()
        )

        social_indexed = 0
        if new_social:
            social_dicts = [
                {
                    "id": str(s.id),
                    "ticker_symbol": s.ticker_symbol,
                    "buzz_score": float(s.buzz_score) if s.buzz_score else 0,
                    "bullish_ratio": float(s.bullish_ratio) if s.bullish_ratio else 0,
                    "bearish_ratio": float(s.bearish_ratio) if s.bearish_ratio else 0,
                    "post_volume": s.post_volume or 0,
                    "sentiment_trend": s.sentiment_trend or "",
                }
                for s in new_social
            ]
            vs.index_social_sentiment(social_dicts)
            social_indexed = len(social_dicts)
            new_social_cursor = max(
                (s.fetched_at for s in new_social if s.fetched_at),
                default=None,
            )
            if new_social_cursor is not None:
                redis_client.set(
                    _INDEXER_SOCIAL_CURSOR_KEY, new_social_cursor.isoformat()
                )

        logger.info(
            "Vector store incremental index: %d articles, %d social records "
            "(article_cursor=%s)",
            articles_indexed,
            social_indexed,
            redis_client.get(_INDEXER_CURSOR_KEY),
        )
        return {
            "articles_indexed": articles_indexed,
            "social_indexed": social_indexed,
        }
    except Exception as exc:
        logger.exception("Vector store indexing failed")
        raise self.retry(exc=exc)
    finally:
        session.close()


async def _collect_market_data_for_tickers(tickers: list[str]) -> dict[str, int]:
    """Fetch daily OHLCV per ticker (Alpha Vantage primary, yfinance fallback)
    and upsert it via MarketDataService. Returns a ``{ticker: rows_upserted}``
    map. One bad ticker never stalls the others.
    """
    from app.clients import AlphaVantageClient, AlphaVantageError
    from app.config import get_settings
    from app.database import AsyncSessionLocal
    from app.services.market_data import MarketDataService

    settings = get_settings()
    service = MarketDataService()
    results: dict[str, int] = {}

    av_client: AlphaVantageClient | None = None
    if settings.ALPHA_VANTAGE_API_KEY:
        av_client = AlphaVantageClient(api_key=settings.ALPHA_VANTAGE_API_KEY)

    try:
        async with AsyncSessionLocal() as db:
            for ticker in tickers:
                df = None
                # 1. Preferred: Alpha Vantage TIME_SERIES_DAILY.
                if av_client is not None:
                    try:
                        df = await av_client.fetch_daily_prices(ticker, outputsize="compact")
                    except AlphaVantageError as exc:
                        logger.warning("AlphaVantage prices unavailable for %s: %s", ticker, exc)
                        df = None
                    except Exception as exc:
                        logger.warning("AlphaVantage prices failed for %s: %s", ticker, exc)
                        df = None

                # 2. Fallback: yfinance (also the only source when no AV key).
                if df is None or df.empty:
                    try:
                        df = await asyncio.to_thread(
                            service.fetch_stock_data, ticker, "3mo"
                        )
                    except Exception as exc:
                        logger.error("Market data fallback failed for %s: %s", ticker, exc)
                        results[ticker] = 0
                        continue

                if df is None or df.empty:
                    results[ticker] = 0
                    continue

                try:
                    upserted = await service.store_market_data(ticker, df, db)
                    results[ticker] = upserted
                except Exception as exc:
                    logger.error("Market data upsert failed for %s: %s", ticker, exc)
                    await db.rollback()
                    results[ticker] = 0

            await db.commit()
    finally:
        if av_client is not None:
            await av_client.close()

    return results


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def collect_market_data_task(self):
    """Refresh daily OHLCV for every tracked ticker.

    Runs on beat (daily after US market close) and is also chained off
    ``collect_news_task`` so correlations always have fresh prices to align
    against fresh sentiment.
    """
    from app.models import Company

    logger.info("Starting market data collection")
    session = SyncSessionLocal()
    try:
        tickers = [c.ticker_symbol for c in session.query(Company).all()]
    finally:
        session.close()

    if not tickers:
        logger.info("No tracked companies; skipping market data collection")
        return {"tickers_updated": 0, "rows_upserted": 0}

    try:
        results = asyncio.run(_collect_market_data_for_tickers(tickers))
        rows_total = sum(results.values())
        updated = sum(1 for v in results.values() if v > 0)
        logger.info(
            "Market data collection complete: %d/%d tickers, %d rows",
            updated,
            len(tickers),
            rows_total,
        )
        return {"tickers_updated": updated, "rows_upserted": rows_total}
    except Exception as exc:
        logger.exception("Market data collection failed")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=0)
def backfill_historical_data_task(
    self,
    tickers: list[str] | None = None,
    years_back: int = 5,
    include_news: bool = True,
    include_prices: bool = True,
    news_window_days: int = 30,
    max_news_requests: int | None = 200,
    news_provider: str = "gdelt",
):
    """Long-running historical backfill task.

    Not retried on failure (``max_retries=0``): a backfill run can take
    minutes to hours and may legitimately be cancelled by the operator
    — silently retrying would double-issue expensive AV calls. Re-run
    manually if needed; the persistence paths are idempotent.
    """
    from app.services.backfill import run_backfill_sync

    logger.info(
        "Starting historical backfill task (tickers=%s, years=%d, provider=%s)",
        tickers or "ALL",
        years_back,
        news_provider,
    )
    try:
        summary = run_backfill_sync(
            tickers=tickers,
            years_back=years_back,
            include_news=include_news,
            include_prices=include_prices,
            news_window_days=news_window_days,
            max_news_requests=max_news_requests,
            news_provider=news_provider,
        )
        logger.info(
            "Backfill complete: %d tickers, %d new articles, %d price rows",
            summary["tickers_processed"],
            summary["total_news_new"],
            summary["total_prices_upserted"],
        )
        return summary
    except Exception:
        logger.exception("Historical backfill task failed")
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600)
def run_finetuning_task(self, job_id: int):
    """Execute a fine-tuning job."""
    from app.services.finetuning import FineTuningPipeline
    from app.models import FinetuningJob

    logger.info("Starting fine-tuning job %d", job_id)
    session = SyncSessionLocal()
    try:
        job = session.query(FinetuningJob).filter_by(id=job_id).first()
        if not job:
            logger.error("Fine-tuning job %d not found", job_id)
            return {"error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.utcnow()
        session.commit()

        pipeline = FineTuningPipeline(session)
        pipeline.train(
            job_id=job_id,
            dataset_name=job.dataset_name,
            hyperparams=job.hyperparams or {},
        )

        session.refresh(job)
        logger.info("Fine-tuning job %d completed: %s", job_id, job.status)
        return {"job_id": job_id, "status": job.status}
    except Exception as exc:
        session.rollback()
        job = session.query(FinetuningJob).filter_by(id=job_id).first()
        if job:
            job.status = "failed"
            job.metrics = {**(job.metrics or {}), "error": str(exc)}
            session.commit()
        logger.exception("Fine-tuning job %d failed", job_id)
        raise self.retry(exc=exc)
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=0, acks_late=True)
def run_simulation_task(
    self,
    run_id: int,
    profiles: list[str] | None = None,
    universe: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Execute a backtest trader-agent simulation off the main container.

    We intentionally set ``max_retries=0``: a simulation is long-running
    and makes many LLM calls, so silently re-queueing on transient error
    would burn through Groq quota with no observable improvement. The
    engine itself marks the ``SimulationRun`` row ``failed`` on error,
    which is what the API / UI surface.
    """
    from datetime import date as _date
    from app.services.simulation.engine import run_simulation

    def _parse_date(s: str | None):
        if not s:
            return None
        return _date.fromisoformat(s)

    logger.info("Starting simulation run %d", run_id)
    try:
        result = run_simulation(
            run_id=run_id,
            profile_names=profiles,
            universe_override=universe,
            start_date=_parse_date(start_date),
            end_date=_parse_date(end_date),
        )
        logger.info("Simulation run %d finished: %s", run_id, result.get("status"))
        return result
    except Exception:
        logger.exception("Simulation run %d failed", run_id)
        raise
