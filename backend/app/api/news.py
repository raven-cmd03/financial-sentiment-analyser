from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import NewsArticle, ArticleCompany, Company
from app.schemas.schemas import NewsArticleOut

router = APIRouter()


@router.get("", response_model=list[NewsArticleOut])
async def list_news(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(NewsArticle)
        .options(selectinload(NewsArticle.sentiment_results))
        .order_by(NewsArticle.publication_date.desc())
    )
    if source:
        stmt = stmt.where(NewsArticle.source == source)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    articles = result.scalars().unique().all()

    return [
        NewsArticleOut(
            article_id=a.article_id,
            title=a.title,
            content=a.content[:500],
            source=a.source,
            url=a.url,
            publication_date=a.publication_date,
            collected_date=a.collected_date,
            sentiment=a.sentiment_results[0] if a.sentiment_results else None,
        )
        for a in articles
    ]


@router.get("/article/{article_id}", response_model=NewsArticleOut)
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.article_id == article_id)
        .options(selectinload(NewsArticle.sentiment_results))
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail=f"Article '{article_id}' not found")

    return NewsArticleOut(
        article_id=article.article_id,
        title=article.title,
        content=article.content,
        source=article.source,
        url=article.url,
        publication_date=article.publication_date,
        collected_date=article.collected_date,
        sentiment=article.sentiment_results[0] if article.sentiment_results else None,
    )


@router.get("/{ticker}", response_model=list[NewsArticleOut])
async def list_news_by_ticker(
    ticker: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    ticker = ticker.upper()

    stmt = (
        select(NewsArticle)
        .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
        .join(Company, Company.company_id == ArticleCompany.company_id)
        .where(Company.ticker_symbol == ticker)
        .options(selectinload(NewsArticle.sentiment_results))
        .order_by(NewsArticle.publication_date.desc())
    )
    if source:
        stmt = stmt.where(NewsArticle.source == source)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    articles = result.scalars().unique().all()

    return [
        NewsArticleOut(
            article_id=a.article_id,
            title=a.title,
            content=a.content[:500],
            source=a.source,
            url=a.url,
            publication_date=a.publication_date,
            collected_date=a.collected_date,
            sentiment=a.sentiment_results[0] if a.sentiment_results else None,
        )
        for a in articles
    ]
