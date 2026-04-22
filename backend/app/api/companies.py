from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Company, NewsArticle, SentimentResult, ArticleCompany, SocialSentiment
from app.schemas.schemas import CompanyOut, CompanySentimentOut, NewsArticleOut, SocialSentimentOut

router = APIRouter()


@router.get("", response_model=list[CompanyOut])
async def list_companies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).order_by(Company.ticker_symbol))
    return result.scalars().all()


@router.get("/{ticker}", response_model=CompanyOut)
async def get_company(ticker: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Company).where(Company.ticker_symbol == ticker.upper())
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company with ticker '{ticker}' not found")
    return company


@router.get("/{ticker}/sentiment", response_model=CompanySentimentOut)
async def get_company_sentiment(ticker: str, db: AsyncSession = Depends(get_db)):
    ticker = ticker.upper()

    result = await db.execute(
        select(Company).where(Company.ticker_symbol == ticker)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company with ticker '{ticker}' not found")

    now = datetime.utcnow()
    cutoff = now - timedelta(days=7)
    prior_cutoff = now - timedelta(days=14)
    articles_result = await db.execute(
        select(NewsArticle)
        .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
        .where(
            ArticleCompany.company_id == company.company_id,
            NewsArticle.publication_date >= prior_cutoff,
        )
        .options(selectinload(NewsArticle.sentiment_results))
        .order_by(NewsArticle.publication_date.desc())
        .limit(100)
    )
    articles = articles_result.scalars().unique().all()

    # Partition articles into the most recent 7d window vs the prior 7d window.
    recent_scores: list = []
    prior_scores: list = []
    for article in articles:
        bucket = recent_scores if article.publication_date >= cutoff else prior_scores
        for sr in article.sentiment_results:
            bucket.append(sr)

    if recent_scores:
        avg_pos = sum(float(s.positive_score) for s in recent_scores) / len(recent_scores)
        avg_neg = sum(float(s.negative_score) for s in recent_scores) / len(recent_scores)
        avg_neu = sum(float(s.neutral_score) for s in recent_scores) / len(recent_scores)
        overall = max(
            ("positive", avg_pos), ("negative", avg_neg), ("neutral", avg_neu),
            key=lambda x: x[1],
        )[0]
    else:
        avg_pos = avg_neg = avg_neu = 0.0
        overall = "neutral"

    net_score = avg_pos - avg_neg

    # Trending: compare net sentiment to prior 7d window (stable unless we have data in both).
    trending = "stable"
    if prior_scores and recent_scores:
        prior_net = (
            sum(float(s.positive_score) - float(s.negative_score) for s in prior_scores)
            / len(prior_scores)
        )
        delta = net_score - prior_net
        if delta > 0.05:
            trending = "up"
        elif delta < -0.05:
            trending = "down"

    social_result = await db.execute(
        select(SocialSentiment)
        .where(SocialSentiment.ticker_symbol == ticker)
        .order_by(SocialSentiment.fetched_at.desc())
        .limit(1)
    )
    social = social_result.scalar_one_or_none()

    recent_articles_out = []
    recent_articles = [a for a in articles if a.publication_date >= cutoff]
    for a in recent_articles[:10]:
        sentinel = a.sentiment_results[0] if a.sentiment_results else None
        recent_articles_out.append(
            NewsArticleOut(
                article_id=a.article_id,
                title=a.title,
                content=a.content[:500],
                source=a.source,
                url=a.url,
                publication_date=a.publication_date,
                collected_date=a.collected_date,
                sentiment=sentinel,
            )
        )

    return CompanySentimentOut(
        company=company,
        overall_sentiment=overall,
        overall_score=round(net_score, 4),
        average_positive=round(avg_pos, 4),
        average_negative=round(avg_neg, 4),
        average_neutral=round(avg_neu, 4),
        article_count=len(recent_scores),
        trending=trending,
        recent_articles=recent_articles_out,
        social=social,
    )


@router.get("/{ticker}/sentiment/history")
async def get_sentiment_history(
    ticker: str, days: int = 30, db: AsyncSession = Depends(get_db)
):
    ticker = ticker.upper()
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            cast(SentimentResult.analyzed_date, Date).label("date"),
            func.avg(SentimentResult.positive_score).label("avg_positive"),
            func.avg(SentimentResult.negative_score).label("avg_negative"),
            func.avg(SentimentResult.neutral_score).label("avg_neutral"),
            func.count(SentimentResult.result_id).label("article_count"),
        )
        .join(NewsArticle, SentimentResult.article_id == NewsArticle.article_id)
        .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
        .join(Company, Company.company_id == ArticleCompany.company_id)
        .where(Company.ticker_symbol == ticker, SentimentResult.analyzed_date >= cutoff)
        .group_by(cast(SentimentResult.analyzed_date, Date))
        .order_by(cast(SentimentResult.analyzed_date, Date))
    )

    rows = result.all()
    return [
        {
            "date": str(row.date),
            "sentiment_score": round(float(row.avg_positive), 4),
            "positive_ratio": round(float(row.avg_positive), 4),
            "negative_ratio": round(float(row.avg_negative), 4),
            "neutral_ratio": round(float(row.avg_neutral), 4),
            "article_count": row.article_count,
        }
        for row in rows
    ]
