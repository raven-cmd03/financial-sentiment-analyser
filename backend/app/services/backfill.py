"""Historical-data backfill service.

Populates the database with the last N years of news + prices so that
correlations, trend charts, and the RAG chat have a dense enough corpus
to be useful from day one.

Constraints baked in:

* **News** — two historical providers are supported:
    - ``gdelt`` (default) — free, no API key, 5+ years of history, 250
      articles per call. Metadata only (title + URL; content is empty
      and FinBERT scores on the title, same as the existing empty-content
      fallback in ``analyze_sentiment_task``).
    - ``alpha_vantage`` — richer summaries + provider sentiment, but
      free tier caps at 25 calls/day. Use only if you have a paid key
      or a small scope.
  ``--news-provider=both`` merges them (dedup by URL hash) for maximum
  coverage. Google News / Yahoo don't support historical date windows
  and cannot contribute to a backfill.
* **Prices** — we prefer yfinance (no rate limit, supports ``period="5y"``
  or explicit ``start``/``end``). Alpha Vantage ``outputsize="full"`` is
  the fallback.
* **Social** — Adanos only exposes point-in-time aggregates, so we
  cannot reconstruct 5 years of X sentiment. The backfill skips social
  and returns a clear note in the summary.

The function is **idempotent**: ``NewsArticle.url`` is unique (with a
SHA-256 ``article_id`` hash), and ``MarketData`` has ``uq_ticker_date``.
Re-running a backfill over the same window is cheap.

FinBERT analysis is dispatched via Celery (``analyze_sentiment_task``)
in batches — we do not load the 440 MB model into the backfill process.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

import pandas as pd

from app.database import AsyncSessionLocal, SyncSessionLocal

logger = logging.getLogger(__name__)

# Alpha Vantage caps each NEWS_SENTIMENT response at 1000 articles. We default
# to ~monthly windows so even very noisy tickers (AAPL, TSLA) rarely truncate.
_DEFAULT_NEWS_WINDOW_DAYS = 30

# Batch size for dispatching Celery sentiment jobs. Each task loads FinBERT
# once, so we want chunks that amortize the model load without hogging the
# worker for minutes.
_SENTIMENT_BATCH_SIZE = 100

# Sanity ceiling to stop runaway fetches if the user doesn't pass one.
_DEFAULT_MAX_NEWS_REQUESTS = 200


@dataclass
class TickerBackfillResult:
    ticker: str
    prices_upserted: int = 0
    news_fetched: int = 0
    news_new: int = 0
    news_requests: int = 0
    errors: list[str] = field(default_factory=list)
    rate_limited: bool = False

    def as_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "prices_upserted": self.prices_upserted,
            "news_fetched": self.news_fetched,
            "news_new": self.news_new,
            "news_requests": self.news_requests,
            "errors": list(self.errors),
            "rate_limited": self.rate_limited,
        }


@dataclass
class BackfillSummary:
    years_back: int
    include_news: bool
    include_prices: bool
    tickers: list[TickerBackfillResult] = field(default_factory=list)
    total_articles_queued_for_sentiment: int = 0
    social_note: str = (
        "Social sentiment history is not available: Adanos only exposes "
        "point-in-time aggregates. Going forward, poll_social_sentiment_task "
        "will continue building the timeline every hour."
    )

    def as_dict(self) -> dict:
        return {
            "years_back": self.years_back,
            "include_news": self.include_news,
            "include_prices": self.include_prices,
            "tickers_processed": len(self.tickers),
            "total_prices_upserted": sum(
                t.prices_upserted for t in self.tickers
            ),
            "total_news_new": sum(t.news_new for t in self.tickers),
            "total_news_requests": sum(t.news_requests for t in self.tickers),
            "total_articles_queued_for_sentiment": self.total_articles_queued_for_sentiment,
            "per_ticker": [t.as_dict() for t in self.tickers],
            "social_note": self.social_note,
        }


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def iter_time_windows(
    *,
    start: datetime,
    end: datetime,
    window_days: int,
) -> Iterable[tuple[datetime, datetime]]:
    """Yield ``(window_start, window_end)`` tuples walking backwards.

    Walking backwards (newest-first) means if the run is interrupted by
    a rate limit we at least have the most recent — and most relevant —
    articles persisted.
    """
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    if end <= start:
        return

    cursor = end
    while cursor > start:
        window_start = max(cursor - timedelta(days=window_days), start)
        yield window_start, cursor
        cursor = window_start


def _chunks(seq: Sequence[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(seq), size):
        yield list(seq[i : i + size])


async def _backfill_prices_for_ticker(
    *,
    ticker: str,
    years_back: int,
    av_client,
    av_error_cls,
    market_service,
    result: TickerBackfillResult,
) -> None:
    """Upsert ``years_back`` years of daily OHLCV for a single ticker.

    Strategy: yfinance first (no rate limit, supports any period), AV
    ``outputsize="full"`` as the fallback. Either way the resulting frame
    goes through the existing ``MarketDataService.store_market_data``
    upsert so we stay idempotent against ``uq_ticker_date``.
    """
    df: pd.DataFrame | None = None

    # 1. yfinance — cheap, no quota, handles arbitrary history.
    try:
        df = await asyncio.to_thread(
            market_service.fetch_stock_data, ticker, f"{years_back}y"
        )
    except Exception as exc:  # pragma: no cover - network-dependent
        logger.warning(
            "yfinance backfill failed for %s: %s — falling back to AV", ticker, exc
        )
        df = None

    # 2. AV full-series fallback.
    if (df is None or df.empty) and av_client is not None:
        try:
            df = await av_client.fetch_daily_prices(ticker, outputsize="full")
        except av_error_cls as exc:
            logger.warning("AV full-series unavailable for %s: %s", ticker, exc)
            result.errors.append(f"prices: AV throttled ({exc})")
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("AV full-series failed for %s: %s", ticker, exc)
            result.errors.append(f"prices: AV error ({exc})")
            return

    if df is None or df.empty:
        logger.info("No price history available for %s", ticker)
        return

    # Trim to exactly ``years_back`` — yfinance "5y" is approximate and AV
    # "full" goes back 20+ years. We want the same bound in both paths so
    # the correlation table doesn't have one ticker with 20 years and
    # another with 5.
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.DateOffset(
        years=years_back
    )
    df = df[df.index >= cutoff]

    if df.empty:
        return

    async with AsyncSessionLocal() as db:
        try:
            upserted = await market_service.store_market_data(ticker, df, db)
            await db.commit()
            result.prices_upserted = upserted
        except Exception as exc:
            await db.rollback()
            logger.exception("Price upsert failed for %s", ticker)
            result.errors.append(f"prices: upsert failed ({exc})")


def _persist_articles_sync(
    session,
    company,
    articles: list[dict],
    news_article_cls,
    article_company_cls,
) -> list[str]:
    """Insert articles + M2M links, skipping duplicates. Returns new IDs.

    Mirrors the logic in ``collect_news_task`` so the backfill lands data
    in exactly the same shape the rest of the pipeline already reads.
    """
    new_ids: list[str] = []
    for a in articles:
        url = (a.get("url") or "").strip()
        if not url:
            continue

        aid = _hash_url(url)
        title = _strip_html(a.get("title") or "")
        content = _strip_html(a.get("content") or a.get("description") or "")
        if not title:
            continue

        pub_date = a.get("publication_date")
        if isinstance(pub_date, str):
            try:
                # Python 3.10's ``fromisoformat`` rejects the trailing
                # ``Z``; GDELT emits ``+00:00`` (fine) but the HF corpus
                # emits ``Z`` (fails). Swap once so both work and we
                # don't silently substitute ``utcnow`` for real dates.
                pub_date = datetime.fromisoformat(
                    pub_date.replace("Z", "+00:00")
                )
                if pub_date.tzinfo is not None:
                    pub_date = pub_date.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, TypeError):
                pub_date = datetime.utcnow()
        elif pub_date is None:
            pub_date = datetime.utcnow()

        existing = (
            session.query(news_article_cls).filter_by(article_id=aid).first()
        )
        if existing:
            # Article already exists; ensure the M2M link for this company
            # is present (an article can mention multiple tickers, and a
            # previous backfill window may have inserted it under a
            # different one).
            link_exists = (
                session.query(article_company_cls)
                .filter_by(article_id=aid, company_id=company.company_id)
                .first()
            )
            if not link_exists:
                try:
                    with session.begin_nested():
                        session.add(
                            article_company_cls(
                                article_id=aid,
                                company_id=company.company_id,
                            )
                        )
                except Exception as link_exc:
                    logger.debug(
                        "Skipping duplicate link %s/%s: %s",
                        aid,
                        company.ticker_symbol,
                        link_exc,
                    )
            continue

        try:
            with session.begin_nested():
                session.add(
                    news_article_cls(
                        article_id=aid,
                        title=title[:2000],
                        content=content[:10000],
                        source=(a.get("source") or "unknown")[:100],
                        url=url,
                        publication_date=pub_date,
                        language="en",
                    )
                )
                session.flush()
                session.add(
                    article_company_cls(
                        article_id=aid,
                        company_id=company.company_id,
                    )
                )
            new_ids.append(aid)
        except Exception as exc:
            logger.warning("Skipping article %s during backfill: %s", aid, exc)

    return new_ids


async def _fetch_window_from_provider(
    *,
    provider: str,
    company,
    window_start: datetime,
    window_end: datetime,
    gdelt_client,
    av_client,
    av_error_cls,
) -> tuple[list[dict], bool]:
    """Fetch one window from one provider.

    Returns ``(articles, rate_limited)``. ``rate_limited=True`` means
    the caller should stop paginating for this ticker.
    """
    if provider == "gdelt":
        if gdelt_client is None:
            return [], False
        # GDELT keyword search: include both ticker and company name so
        # we catch headlines that mention only one variant. Two gotchas
        # from GDELT's parser, learned empirically:
        #   1. Short quoted phrases (<~2 words, ~5 chars) are rejected
        #      with "The specified phrase is too short." — so the
        #      ticker goes in *unquoted*.
        #   2. Trailing legal-suffix punctuation in "Apple Inc.",
        #      "Tesla, Inc." breaks the quoted-phrase lexer — strip it.
        # ``OR``-queries must also be wrapped in parens (handled by
        # the client's ``_build_query``).
        company_clean = company.company_name.strip().rstrip(".,;:")
        query = f'{company.ticker_symbol} OR "{company_clean}"'
        articles = await gdelt_client.fetch_news(
            query,
            max_results=250,
            time_from=window_start,
            time_to=window_end,
            sort="DateDesc",
        )
        return articles, False

    if provider == "alpha_vantage":
        if av_client is None:
            return [], False
        try:
            articles = await av_client.fetch_news(
                company.ticker_symbol,
                max_results=1000,
                time_from=window_start,
                time_to=window_end,
                # EARLIEST so if AV truncates a noisy window we still
                # get the oldest side (which we otherwise never see).
                sort="EARLIEST",
                raise_on_rate_limit=True,
            )
            return articles, False
        except av_error_cls as exc:
            logger.warning(
                "AV rate limit hit for %s window %s..%s: %s",
                company.ticker_symbol,
                window_start.date(),
                window_end.date(),
                exc,
            )
            return [], True

    return [], False


async def _backfill_news_for_ticker(
    *,
    company,
    years_back: int,
    window_days: int,
    max_requests: int,
    providers: list[str],
    gdelt_client,
    av_client,
    av_error_cls,
    session,
    news_article_cls,
    article_company_cls,
    result: TickerBackfillResult,
    new_ids_bucket: list[str],
) -> None:
    """Paginate news across time windows and persist, per provider.

    ``providers`` is an ordered list — each is walked over the full
    window grid in turn, which means Alpha Vantage (if included)
    complements whatever GDELT already pulled. Duplicate URLs are
    filtered at persist time by the unique ``article_id`` constraint.

    Stops early on rate-limit or when ``max_requests`` is reached.
    """
    if not providers:
        result.errors.append("news: no providers configured")
        return

    end = datetime.utcnow()
    start = end - timedelta(days=365 * years_back)
    requests_made = 0

    for provider in providers:
        # Each provider has its own generator so if AV rate-limits out
        # in the middle of its pass, GDELT's pass is unaffected.
        for window_start, window_end in iter_time_windows(
            start=start, end=end, window_days=window_days
        ):
            if requests_made >= max_requests:
                logger.info(
                    "Hit max_news_requests=%d for %s; stopping early",
                    max_requests,
                    company.ticker_symbol,
                )
                result.news_requests = requests_made
                return

            requests_made += 1
            try:
                articles, rate_limited = await _fetch_window_from_provider(
                    provider=provider,
                    company=company,
                    window_start=window_start,
                    window_end=window_end,
                    gdelt_client=gdelt_client,
                    av_client=av_client,
                    av_error_cls=av_error_cls,
                )
            except Exception as exc:
                logger.exception(
                    "News fetch failed for %s (%s) window %s..%s",
                    company.ticker_symbol,
                    provider,
                    window_start.date(),
                    window_end.date(),
                )
                result.errors.append(f"news[{provider}]: {exc}")
                continue

            if rate_limited:
                result.errors.append(
                    f"news[{provider}]: rate-limited; skipping remaining windows"
                )
                result.rate_limited = True
                # Skip this provider's remaining windows but let the
                # next provider (if any) still run.
                break

            result.news_fetched += len(articles)

            if not articles:
                continue

            try:
                new_ids = _persist_articles_sync(
                    session,
                    company,
                    articles,
                    news_article_cls,
                    article_company_cls,
                )
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.exception(
                    "Persist failed for %s (%s) window %s..%s",
                    company.ticker_symbol,
                    provider,
                    window_start.date(),
                    window_end.date(),
                )
                result.errors.append(f"news[{provider}]: persist failed ({exc})")
                continue

            result.news_new += len(new_ids)
            new_ids_bucket.extend(new_ids)

    result.news_requests = requests_made


_VALID_NEWS_PROVIDERS = ("gdelt", "alpha_vantage", "both")


async def run_backfill(
    *,
    tickers: Sequence[str] | None = None,
    years_back: int = 5,
    include_news: bool = True,
    include_prices: bool = True,
    news_window_days: int = _DEFAULT_NEWS_WINDOW_DAYS,
    max_news_requests: int | None = _DEFAULT_MAX_NEWS_REQUESTS,
    news_provider: str = "gdelt",
    dispatch_sentiment: bool = True,
) -> BackfillSummary:
    """Populate news + prices for the last ``years_back`` years.

    Parameters
    ----------
    tickers
        Tickers to backfill. ``None`` means every company in the DB.
    years_back
        Number of years of history to pull. Default 5.
    include_news / include_prices
        Turn either leg off for targeted re-runs.
    news_window_days
        Per-call window size. 30 days is a sweet spot — noisy tickers
        rarely hit the per-call cap (AV: 1000, GDELT: 250), quiet
        tickers don't waste calls.
    max_news_requests
        Soft cap on news calls *per ticker* to protect free-tier
        quotas. Set to ``None`` to disable. When ``news_provider="both"``,
        the cap is shared across both providers.
    news_provider
        One of ``"gdelt"`` (default, free, no key required, 5+ yrs of
        history), ``"alpha_vantage"`` (requires ``ALPHA_VANTAGE_API_KEY``;
        free tier is 25/day), or ``"both"`` (GDELT first, then AV — the
        second pass complements with richer summaries and tickers AV
        covers better, dedup is free via the URL-hash unique index).
    dispatch_sentiment
        If ``True``, enqueue ``analyze_sentiment_task`` batches after
        articles are persisted. Set ``False`` for tests / dry runs.

    Returns
    -------
    BackfillSummary
        Per-ticker counts and any errors encountered. Social sentiment
        is explicitly noted as unavailable for backfill.
    """
    # Imports kept local: this module is loaded by a Celery task which
    # in turn imports SentimentAnalyzer/transformers on its own path — we
    # don't want to drag those in here unnecessarily.
    from app.clients import (
        AlphaVantageClient,
        AlphaVantageError,
        GdeltClient,
    )
    from app.config import get_settings
    from app.models import ArticleCompany, Company, NewsArticle
    from app.services.market_data import MarketDataService

    if news_provider not in _VALID_NEWS_PROVIDERS:
        raise ValueError(
            f"news_provider must be one of {_VALID_NEWS_PROVIDERS}, got {news_provider!r}"
        )

    settings = get_settings()
    summary = BackfillSummary(
        years_back=years_back,
        include_news=include_news,
        include_prices=include_prices,
    )

    session = SyncSessionLocal()
    try:
        query = session.query(Company)
        if tickers:
            upper = [t.upper() for t in tickers]
            query = query.filter(Company.ticker_symbol.in_(upper))
        companies = query.all()

        if not companies:
            logger.warning("No companies match tickers=%s; nothing to backfill", tickers)
            return summary

        market_service = MarketDataService()

        av_client: AlphaVantageClient | None = None
        if settings.ALPHA_VANTAGE_API_KEY:
            av_client = AlphaVantageClient(
                api_key=settings.ALPHA_VANTAGE_API_KEY
            )

        gdelt_client: GdeltClient | None = None
        if news_provider in ("gdelt", "both"):
            gdelt_client = GdeltClient()

        # Resolve the ordered provider list for the news pass. If the
        # operator asked for AV but we have no key, we fall back to
        # GDELT with a loud warning rather than silently returning 0.
        providers: list[str] = []
        if include_news:
            if news_provider == "gdelt":
                providers = ["gdelt"]
            elif news_provider == "alpha_vantage":
                if av_client is None:
                    logger.warning(
                        "alpha_vantage requested but ALPHA_VANTAGE_API_KEY is empty; "
                        "falling back to GDELT"
                    )
                    if gdelt_client is None:
                        gdelt_client = GdeltClient()
                    providers = ["gdelt"]
                else:
                    providers = ["alpha_vantage"]
            elif news_provider == "both":
                providers = ["gdelt"]
                if av_client is not None:
                    providers.append("alpha_vantage")

        effective_max = (
            max_news_requests
            if max_news_requests is not None
            else 10_000  # basically unbounded
        )

        all_new_ids: list[str] = []

        try:
            for company in companies:
                result = TickerBackfillResult(ticker=company.ticker_symbol)
                summary.tickers.append(result)

                logger.info(
                    "Backfilling %s (years=%d, news=%s[%s], prices=%s)",
                    company.ticker_symbol,
                    years_back,
                    include_news,
                    ",".join(providers) if providers else "-",
                    include_prices,
                )

                if include_prices:
                    await _backfill_prices_for_ticker(
                        ticker=company.ticker_symbol,
                        years_back=years_back,
                        av_client=av_client,
                        av_error_cls=AlphaVantageError,
                        market_service=market_service,
                        result=result,
                    )

                if include_news and providers:
                    ticker_new_ids: list[str] = []
                    await _backfill_news_for_ticker(
                        company=company,
                        years_back=years_back,
                        window_days=news_window_days,
                        max_requests=effective_max,
                        providers=providers,
                        gdelt_client=gdelt_client,
                        av_client=av_client,
                        av_error_cls=AlphaVantageError,
                        session=session,
                        news_article_cls=NewsArticle,
                        article_company_cls=ArticleCompany,
                        result=result,
                        new_ids_bucket=ticker_new_ids,
                    )
                    all_new_ids.extend(ticker_new_ids)
        finally:
            if av_client is not None:
                await av_client.close()
            if gdelt_client is not None:
                await gdelt_client.close()

        # Dispatch sentiment analysis in batches. We do this at the end
        # so the Celery worker queue isn't hammered mid-backfill.
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


def run_backfill_sync(**kwargs) -> dict:
    """Sync wrapper for Celery / CLI entry points.

    Returns the summary as a plain dict (Celery-serialisable).
    """
    summary = asyncio.run(run_backfill(**kwargs))
    return summary.as_dict()
