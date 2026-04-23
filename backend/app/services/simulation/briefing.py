"""Build the per-day briefing payload that each agent sees.

``build_briefing(date, universe, session, variant)`` returns a nested
dict with a fixed structure regardless of variant — only the *content*
of the per-ticker entries differs:

- treatment: price metrics + sentiment rollup + recent headlines
- control: price metrics + 20-day volatility + 52-week high/low

The contract is "nothing beyond ``date - 1`` close". Enforcing that in
one place keeps look-ahead bugs out of the engine.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import (
    ArticleCompany,
    Company,
    MarketData,
    NewsArticle,
    SentimentResult,
)

Variant = Literal["treatment", "control"]
logger = logging.getLogger(__name__)


# Number of trailing trading days we pull for price metrics. 252 covers
# a year so the control arm can compute a proper 52-week high/low and
# the treatment arm still has headroom for 7/30-day trend features.
_PRICE_LOOKBACK_DAYS = 400  # calendar days, filtered to trading days later


def _to_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _pct_change(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or prev == 0:
        return None
    return (curr - prev) / prev


def _stddev(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var) if var >= 0 else None


def _price_history(
    session: Session, ticker: str, cutoff: date_cls
) -> list[MarketData]:
    """Return MarketData rows for ``ticker`` with date <= cutoff, oldest-first.

    Capped at the most recent ``_PRICE_LOOKBACK_DAYS`` calendar days to
    keep the query cheap even on years-deep histories.
    """
    earliest = cutoff - timedelta(days=_PRICE_LOOKBACK_DAYS)
    rows = (
        session.query(MarketData)
        .filter(MarketData.ticker_symbol == ticker)
        .filter(MarketData.date >= earliest)
        .filter(MarketData.date <= cutoff)
        .order_by(MarketData.date.asc())
        .all()
    )
    return rows


def _price_metrics(rows: list[MarketData]) -> dict:
    """Compute the price-only metrics shared by both variants."""
    if not rows:
        return {"last_close": None, "last_date": None}

    closes = [_to_float(r.close_price) for r in rows]
    last_close = closes[-1]
    last_date = rows[-1].date.isoformat() if rows[-1].date else None
    volume = int(rows[-1].volume) if rows[-1].volume else None

    ret_1d = _pct_change(closes[-1], closes[-2]) if len(closes) >= 2 else None
    ret_7d = (
        _pct_change(closes[-1], closes[-8]) if len(closes) >= 8 else None
    )
    ret_30d = (
        _pct_change(closes[-1], closes[-31]) if len(closes) >= 31 else None
    )

    return {
        "last_close": last_close,
        "last_date": last_date,
        "volume": volume,
        "ret_1d": ret_1d,
        "ret_7d": ret_7d,
        "ret_30d": ret_30d,
    }


def _control_extras(rows: list[MarketData]) -> dict:
    """Price-only technicals used as a fair baseline for the control arm.

    We deliberately add 20-day volatility and 52-week high/low so the
    control agent has an alternative signal to the sentiment rollups it
    can't see — otherwise the comparison is trivially unfair.
    """
    closes = [_to_float(r.close_price) for r in rows if r.close_price is not None]
    if not closes:
        return {
            "vol_20d": None,
            "high_52w": None,
            "low_52w": None,
            "pct_off_52w_high": None,
        }

    last = closes[-1]
    last_20 = closes[-20:] if len(closes) >= 20 else closes
    daily_rets_20 = [
        _pct_change(last_20[i], last_20[i - 1])
        for i in range(1, len(last_20))
        if last_20[i - 1]
    ]
    daily_rets_20 = [r for r in daily_rets_20 if r is not None]
    vol_20 = _stddev(daily_rets_20)

    last_252 = closes[-252:] if len(closes) >= 252 else closes
    high_52w = max(last_252) if last_252 else None
    low_52w = min(last_252) if last_252 else None
    pct_off_high = None
    if high_52w and high_52w > 0 and last is not None:
        pct_off_high = (last - high_52w) / high_52w

    return {
        "vol_20d": vol_20,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "pct_off_52w_high": pct_off_high,
    }


def _sentiment_rollup(
    session: Session, ticker: str, cutoff: date_cls
) -> dict:
    """7-day sentiment summary for ``ticker`` ending on ``cutoff`` (inclusive).

    Aggregates articles that have both a SentimentResult and a company
    junction to the given ticker. Published dates strictly <= cutoff end-
    of-day; we normalise to midnight after cutoff to include that trading
    day's pre-close articles.
    """
    window_start = datetime.combine(cutoff - timedelta(days=6), datetime.min.time())
    window_end = datetime.combine(cutoff, datetime.max.time())

    company = (
        session.query(Company).filter(Company.ticker_symbol == ticker).first()
    )
    if not company:
        return _empty_sentiment_rollup()

    q = (
        session.query(
            NewsArticle.publication_date,
            SentimentResult.sentiment_label,
            SentimentResult.positive_score,
            SentimentResult.negative_score,
            SentimentResult.neutral_score,
        )
        .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
        .join(
            SentimentResult, SentimentResult.article_id == NewsArticle.article_id
        )
        .filter(ArticleCompany.company_id == company.company_id)
        .filter(NewsArticle.publication_date >= window_start)
        .filter(NewsArticle.publication_date <= window_end)
    )
    rows = q.all()
    if not rows:
        return _empty_sentiment_rollup()

    counts = defaultdict(int)
    scores: list[float] = []
    by_day: dict[date_cls, list[float]] = defaultdict(list)
    for pub_date, label, pos, neg, neu in rows:
        lbl = (label or "").lower()
        if "pos" in lbl:
            counts["positive"] += 1
        elif "neg" in lbl:
            counts["negative"] += 1
        else:
            counts["neutral"] += 1

        # Compact per-article sentiment score in [-1, +1].
        pos_f = _to_float(pos) or 0.0
        neg_f = _to_float(neg) or 0.0
        s = pos_f - neg_f
        scores.append(s)
        if pub_date:
            by_day[pub_date.date()].append(s)

    mean_score = sum(scores) / len(scores) if scores else 0.0

    # Trend: slope of per-day mean score over the window using a simple
    # linear fit (enough signal for an LLM briefing; we don't need stats).
    day_means = sorted(
        (d, sum(v) / len(v)) for d, v in by_day.items() if v
    )
    trend = None
    if len(day_means) >= 3:
        xs = list(range(len(day_means)))
        ys = [m for _, m in day_means]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        if den > 0:
            trend = num / den

    return {
        "article_count": len(rows),
        "pos_count": counts["positive"],
        "neg_count": counts["negative"],
        "neu_count": counts["neutral"],
        "mean_score": mean_score,
        "trend_slope": trend,
        "per_day_mean": [
            {"date": d.isoformat(), "mean": round(m, 4)} for d, m in day_means
        ],
    }


def _empty_sentiment_rollup() -> dict:
    return {
        "article_count": 0,
        "pos_count": 0,
        "neg_count": 0,
        "neu_count": 0,
        "mean_score": 0.0,
        "trend_slope": None,
        "per_day_mean": [],
    }


def _recent_headlines(
    session: Session, ticker: str, cutoff: date_cls, n: int = 3
) -> list[dict]:
    """Return up to ``n`` most recent headlines for ``ticker`` on or before
    ``cutoff``, each annotated with its sentiment label if we have one.
    """
    window_end = datetime.combine(cutoff, datetime.max.time())
    company = (
        session.query(Company).filter(Company.ticker_symbol == ticker).first()
    )
    if not company:
        return []

    rows = (
        session.query(
            NewsArticle.title,
            NewsArticle.source,
            NewsArticle.publication_date,
            SentimentResult.sentiment_label,
        )
        .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
        .outerjoin(
            SentimentResult, SentimentResult.article_id == NewsArticle.article_id
        )
        .filter(ArticleCompany.company_id == company.company_id)
        .filter(NewsArticle.publication_date <= window_end)
        .order_by(NewsArticle.publication_date.desc())
        .limit(n)
        .all()
    )
    return [
        {
            "title": title,
            "source": source,
            "date": pub.isoformat() if pub else None,
            "sentiment": (label or "").lower() or None,
        }
        for title, source, pub, label in rows
    ]


def build_briefing(
    cutoff: date_cls,
    universe: list[str],
    session: Session,
    variant: Variant,
) -> dict:
    """Build the per-day agent briefing.

    Parameters
    ----------
    cutoff:
        Briefing uses data with ``date <= cutoff``. This is typically
        ``D - 1`` where ``D`` is the decision day; fills happen on the
        next day's open price.
    universe:
        Ticker symbols the agent may trade. The briefing is produced for
        each, silently skipping any ticker with no price history at all.
    session:
        Synchronous SQLAlchemy session.
    variant:
        ``"treatment"`` adds a ``sentiment`` block + recent headlines
        per ticker. ``"control"`` adds 20-day vol / 52-week hi-lo
        instead. Nothing sentiment-derived ever leaks to the control arm.
    """
    if variant not in ("treatment", "control"):
        raise ValueError(f"variant must be 'treatment' or 'control', got {variant!r}")

    tickers: dict[str, dict] = {}
    for ticker in universe:
        rows = _price_history(session, ticker, cutoff)
        if not rows:
            logger.debug("No price history for %s up to %s", ticker, cutoff)
            continue
        entry = _price_metrics(rows)
        if variant == "treatment":
            entry["sentiment"] = _sentiment_rollup(session, ticker, cutoff)
            entry["headlines"] = _recent_headlines(session, ticker, cutoff, n=3)
        else:
            entry.update(_control_extras(rows))
        tickers[ticker] = entry

    return {
        "as_of": cutoff.isoformat(),
        "variant": variant,
        "universe": list(tickers.keys()),
        "tickers": tickers,
    }
