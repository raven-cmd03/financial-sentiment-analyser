"""Correlation service tests.

Covers:
1. The pure statistical helpers (`pearson_correlation`, `spearman_correlation`,
   `time_lagged_correlation`, `rolling_correlation`).
2. Per-ticker filtering in `_load_aligned_data` — the bug where sentiment was
   aggregated globally regardless of the ticker argument.
"""

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from datetime import datetime, timedelta

from app.database import Base
from app.models.company import Company
from app.models.correlation import Correlation  # noqa: F401 (register table)
from app.models.market_data import MarketData
from app.models.news_article import ArticleCompany, NewsArticle
from app.models.sentiment_result import SentimentResult
from app.services.correlation import CorrelationCalculator


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------


def test_pearson_correlation_perfect_positive():
    r, p = CorrelationCalculator.pearson_correlation([1, 2, 3, 4], [2, 4, 6, 8])
    assert r == pytest.approx(1.0)
    assert p < 0.05


def test_pearson_correlation_perfect_negative():
    r, _ = CorrelationCalculator.pearson_correlation([1, 2, 3, 4], [4, 3, 2, 1])
    assert r == pytest.approx(-1.0)


def test_time_lagged_correlation_returns_safe_default_on_short_input():
    r, p = CorrelationCalculator.time_lagged_correlation([1, 2], [1, 2], lag=2)
    assert r == 0.0
    assert p == 1.0


def test_rolling_correlation_window_shape():
    x = list(range(10))
    y = [v * 2 for v in x]
    out = CorrelationCalculator.rolling_correlation(x, y, window=3)
    # First (window-1) values are NaN-> None, rest are ~1.0
    assert out[:2] == [None, None]
    assert all(v == pytest.approx(1.0) for v in out[2:])


# ---------------------------------------------------------------------------
# Per-ticker filtering
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


async def _seed_two_tickers(session):
    """Seed AAPL with strongly positive sentiment and GOOG with strongly
    negative sentiment. Also seed aligned prices."""
    today = datetime.utcnow().date()
    aapl = Company(ticker_symbol="AAPL", company_name="Apple")
    goog = Company(ticker_symbol="GOOG", company_name="Alphabet")
    session.add_all([aapl, goog])
    await session.flush()

    # 10 days of articles + sentiment + prices for both tickers.
    for i in range(10):
        day = datetime.utcnow() - timedelta(days=9 - i)
        for company, pos, neg in (
            (aapl, 0.9, 0.05),
            (goog, 0.05, 0.9),
        ):
            article_id = f"{company.ticker_symbol}-{i}"
            session.add(
                NewsArticle(
                    article_id=article_id,
                    title="t",
                    content="c",
                    source="s",
                    publication_date=day,
                    collected_date=day,
                )
            )
            await session.flush()
            session.add(
                ArticleCompany(article_id=article_id, company_id=company.company_id)
            )
            session.add(
                SentimentResult(
                    article_id=article_id,
                    sentiment_label="positive" if pos > neg else "negative",
                    positive_score=pos,
                    negative_score=neg,
                    neutral_score=1 - pos - neg,
                    confidence=max(pos, neg),
                    analyzed_date=day,
                )
            )
            # Price: AAPL trends up, GOOG trends down.
            price_base = 100.0 + i if company is aapl else 100.0 - i
            session.add(
                MarketData(
                    ticker_symbol=company.ticker_symbol,
                    date=day.date(),
                    open_price=price_base,
                    close_price=price_base + 0.5,
                    high_price=price_base + 1,
                    low_price=price_base - 1,
                    volume=1000,
                )
            )
    await session.commit()


@pytest.mark.asyncio
async def test_load_aligned_data_filters_by_ticker(db_session):
    await _seed_two_tickers(db_session)

    calc = CorrelationCalculator()
    sent_aapl, _ = await calc._load_aligned_data("AAPL", db_session, days=30)
    sent_goog, _ = await calc._load_aligned_data("GOOG", db_session, days=30)

    # AAPL sentiment is ~ (+0.9 - 0.05) = 0.85 per row; GOOG is the opposite.
    # If the ticker filter was missing we'd get a mix of both (close to zero).
    assert sent_aapl.size > 0
    assert sent_goog.size > 0
    assert np.mean(sent_aapl) > 0.5
    assert np.mean(sent_goog) < -0.5
