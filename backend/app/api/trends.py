from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Trend, SentimentResult, NewsArticle, ArticleCompany, Company
from app.schemas.schemas import TrendOut

router = APIRouter()


@router.get("")
async def get_market_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return daily aggregated sentiment across all companies.

    Bucketed by ``NewsArticle.publication_date`` (when the article was
    *written*). Using ``analyzed_date`` here would pile every
    backfilled article onto whichever day FinBERT happened to score
    it, producing a meaningless spike.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            cast(NewsArticle.publication_date, Date).label("date"),
            func.avg(SentimentResult.positive_score).label("avg_positive"),
            func.avg(SentimentResult.negative_score).label("avg_negative"),
            func.avg(SentimentResult.neutral_score).label("avg_neutral"),
            func.count(SentimentResult.result_id).label("article_count"),
        )
        .join(NewsArticle, SentimentResult.article_id == NewsArticle.article_id)
        .where(NewsArticle.publication_date >= cutoff)
        .group_by(cast(NewsArticle.publication_date, Date))
        .order_by(cast(NewsArticle.publication_date, Date))
    )
    rows = result.all()
    return [
        {
            "date": str(row.date),
            # Net sentiment on [-1, 1]: avg(positive_score) - avg(negative_score).
            "sentiment_score": round(float(row.avg_positive) - float(row.avg_negative), 4),
            "positive_ratio": round(float(row.avg_positive), 4),
            "negative_ratio": round(float(row.avg_negative), 4),
            "neutral_ratio": round(float(row.avg_neutral), 4),
            "article_count": row.article_count,
        }
        for row in rows
    ]


@router.get("/{ticker}")
async def get_company_trends(
    ticker: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Return daily aggregated sentiment for a specific company.

    Same publication-date bucketing as ``get_market_trends`` — see
    that docstring for the rationale.
    """
    ticker = ticker.upper()
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            cast(NewsArticle.publication_date, Date).label("date"),
            func.avg(SentimentResult.positive_score).label("avg_positive"),
            func.avg(SentimentResult.negative_score).label("avg_negative"),
            func.avg(SentimentResult.neutral_score).label("avg_neutral"),
            func.count(SentimentResult.result_id).label("article_count"),
        )
        .join(NewsArticle, SentimentResult.article_id == NewsArticle.article_id)
        .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
        .join(Company, Company.company_id == ArticleCompany.company_id)
        .where(
            Company.ticker_symbol == ticker,
            NewsArticle.publication_date >= cutoff,
        )
        .group_by(cast(NewsArticle.publication_date, Date))
        .order_by(cast(NewsArticle.publication_date, Date))
    )
    rows = result.all()
    if not rows:
        return []
    return [
        {
            "date": str(row.date),
            "sentiment_score": round(float(row.avg_positive) - float(row.avg_negative), 4),
            "positive_ratio": round(float(row.avg_positive), 4),
            "negative_ratio": round(float(row.avg_negative), 4),
            "neutral_ratio": round(float(row.avg_neutral), 4),
            "article_count": row.article_count,
        }
        for row in rows
    ]
