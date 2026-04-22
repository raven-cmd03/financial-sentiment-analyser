import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_sentiment import SocialSentiment

logger = logging.getLogger(__name__)

CACHE_TTL_SOCIAL = 3600  # 1 hour


class SocialSentimentService:
    def __init__(self, adanos_client):
        """
        Parameters
        ----------
        adanos_client : app.clients.adanos.AdanosClient
            Pre-configured client for the Adanos X-sentiment API.
        """
        self.adanos = adanos_client

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    async def fetch_social_sentiment(
        self, ticker: str, redis_client=None
    ) -> dict:
        """Fetch X (Twitter) sentiment from Adanos, with optional Redis cache."""
        if redis_client:
            cached = await self._get_cache(ticker, redis_client)
            if cached is not None:
                return cached

        logger.info("Fetching social sentiment for %s from Adanos", ticker)
        try:
            data: dict = await self.adanos.get_sentiment(ticker)
            normalized = {
                "ticker_symbol": ticker,
                "buzz_score": data.get("buzz_score"),
                "bullish_ratio": data.get("bullish_ratio"),
                "bearish_ratio": data.get("bearish_ratio"),
                "post_volume": data.get("post_volume"),
                "sentiment_trend": data.get("sentiment_trend"),
            }
            if redis_client:
                await self._set_cache(ticker, normalized, redis_client)
            return normalized
        except Exception:
            logger.exception("Failed to fetch social sentiment for %s", ticker)
            raise

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def store_social_sentiment(
        self, ticker: str, data: dict, db: AsyncSession
    ) -> SocialSentiment:
        """Persist a social-sentiment snapshot to the database."""
        record = SocialSentiment(
            ticker_symbol=ticker,
            buzz_score=data.get("buzz_score"),
            bullish_ratio=data.get("bullish_ratio"),
            bearish_ratio=data.get("bearish_ratio"),
            post_volume=data.get("post_volume"),
            sentiment_trend=data.get("sentiment_trend"),
        )
        db.add(record)
        try:
            await db.flush()
            logger.info("Stored social sentiment for %s", ticker)
        except Exception:
            logger.exception("Failed to store social sentiment for %s", ticker)
            raise
        return record

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def get_latest(
        self, ticker: str, db: AsyncSession
    ) -> Optional[dict]:
        """Return the most recent social-sentiment row for a ticker."""
        result = await db.execute(
            select(SocialSentiment)
            .where(SocialSentiment.ticker_symbol == ticker)
            .order_by(SocialSentiment.fetched_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "ticker_symbol": row.ticker_symbol,
            "buzz_score": float(row.buzz_score) if row.buzz_score else None,
            "bullish_ratio": float(row.bullish_ratio) if row.bullish_ratio else None,
            "bearish_ratio": float(row.bearish_ratio) if row.bearish_ratio else None,
            "post_volume": row.post_volume,
            "sentiment_trend": row.sentiment_trend,
            "fetched_at": str(row.fetched_at) if row.fetched_at else None,
        }

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    async def _get_cache(self, ticker: str, redis_client) -> Optional[dict]:
        cache_key = f"social:{ticker}"
        try:
            raw = await redis_client.get(cache_key)
            if raw:
                logger.debug("Social cache hit for %s", ticker)
                return json.loads(raw)
        except Exception:
            logger.warning("Redis read failed for social:%s", ticker)
        return None

    async def _set_cache(self, ticker: str, data: dict, redis_client) -> None:
        cache_key = f"social:{ticker}"
        try:
            await redis_client.set(cache_key, json.dumps(data), ex=CACHE_TTL_SOCIAL)
        except Exception:
            logger.warning("Redis write failed for social:%s", ticker)
