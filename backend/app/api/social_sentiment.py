from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import SocialSentiment
from app.schemas.schemas import SocialSentimentOut

router = APIRouter()


@router.get("/trending/top", response_model=list[SocialSentimentOut])
async def get_trending(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Top trending tickers by buzz score (latest snapshot per ticker)."""
    latest_subq = (
        select(
            SocialSentiment.ticker_symbol,
            SocialSentiment.id,
        )
        .distinct(SocialSentiment.ticker_symbol)
        .order_by(SocialSentiment.ticker_symbol, desc(SocialSentiment.fetched_at))
        .subquery()
    )

    result = await db.execute(
        select(SocialSentiment)
        .where(SocialSentiment.id.in_(select(latest_subq.c.id)))
        .order_by(desc(SocialSentiment.buzz_score))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{ticker}", response_model=SocialSentimentOut)
async def get_social_sentiment(ticker: str, db: AsyncSession = Depends(get_db)):
    ticker = ticker.upper()
    result = await db.execute(
        select(SocialSentiment)
        .where(SocialSentiment.ticker_symbol == ticker)
        .order_by(desc(SocialSentiment.fetched_at))
        .limit(1)
    )
    sentiment = result.scalar_one_or_none()
    if not sentiment:
        raise HTTPException(status_code=404, detail=f"No social sentiment data for '{ticker}'")
    return sentiment


@router.get("/{ticker}/history", response_model=list[SocialSentimentOut])
async def get_social_sentiment_history(
    ticker: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    ticker = ticker.upper()
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(SocialSentiment)
        .where(
            SocialSentiment.ticker_symbol == ticker,
            SocialSentiment.fetched_at >= cutoff,
        )
        .order_by(SocialSentiment.fetched_at.desc())
    )
    return result.scalars().all()
