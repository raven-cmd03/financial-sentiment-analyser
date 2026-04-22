import json
import logging
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import MarketData

logger = logging.getLogger(__name__)

CACHE_TTL_REALTIME = 300       # 5 minutes
CACHE_TTL_HISTORICAL = 86400   # 24 hours


class MarketDataService:
    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    def fetch_stock_data(
        self, ticker: str, period: str = "1mo"
    ) -> pd.DataFrame:
        """Download OHLCV data from Yahoo Finance."""
        logger.info("Fetching stock data for %s (period=%s)", ticker, period)
        try:
            stock = yf.Ticker(ticker)
            df: pd.DataFrame = stock.history(period=period)
            if df.empty:
                logger.warning("No data returned for %s", ticker)
                return df
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df.rename(columns={
                "Open": "open_price",
                "High": "high_price",
                "Low": "low_price",
                "Close": "close_price",
                "Volume": "volume",
            })
            return df[["open_price", "high_price", "low_price", "close_price", "volume"]]
        except Exception:
            logger.exception("Failed to fetch stock data for %s", ticker)
            raise

    # ------------------------------------------------------------------
    # Storage (upsert)
    # ------------------------------------------------------------------

    async def store_market_data(
        self, ticker: str, df: pd.DataFrame, db: AsyncSession
    ) -> int:
        """Upsert OHLCV rows into the market_data table. Returns upserted count."""
        if df.empty:
            return 0

        rows_upserted = 0
        for date, row in df.iterrows():
            stmt = (
                pg_insert(MarketData)
                .values(
                    ticker_symbol=ticker,
                    date=date.date(),
                    open_price=round(float(row["open_price"]), 2),
                    close_price=round(float(row["close_price"]), 2),
                    high_price=round(float(row["high_price"]), 2),
                    low_price=round(float(row["low_price"]), 2),
                    volume=int(row["volume"]),
                )
                .on_conflict_do_update(
                    constraint="uq_ticker_date",
                    set_={
                        "open_price": round(float(row["open_price"]), 2),
                        "close_price": round(float(row["close_price"]), 2),
                        "high_price": round(float(row["high_price"]), 2),
                        "low_price": round(float(row["low_price"]), 2),
                        "volume": int(row["volume"]),
                    },
                )
            )
            await db.execute(stmt)
            rows_upserted += 1

        try:
            await db.flush()
            logger.info("Upserted %d market data rows for %s", rows_upserted, ticker)
        except Exception:
            logger.exception("Failed to store market data for %s", ticker)
            raise

        return rows_upserted

    # ------------------------------------------------------------------
    # Redis cache
    # ------------------------------------------------------------------

    async def get_cached_data(
        self, ticker: str, redis_client, realtime: bool = True
    ) -> Optional[dict]:
        """Return cached market data from Redis if available."""
        cache_key = f"market:{ticker}:{'rt' if realtime else 'hist'}"
        try:
            raw = await redis_client.get(cache_key)
            if raw:
                logger.debug("Cache hit for %s", cache_key)
                return json.loads(raw)
        except Exception:
            logger.warning("Redis read failed for %s", cache_key)
        return None

    async def set_cache(
        self, ticker: str, data: dict, redis_client, realtime: bool = True
    ) -> None:
        cache_key = f"market:{ticker}:{'rt' if realtime else 'hist'}"
        ttl = CACHE_TTL_REALTIME if realtime else CACHE_TTL_HISTORICAL
        try:
            await redis_client.set(cache_key, json.dumps(data), ex=ttl)
        except Exception:
            logger.warning("Redis write failed for %s", cache_key)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def get_latest_prices(
        self, ticker: str, db: AsyncSession, limit: int = 30
    ) -> list[dict]:
        """Return the most recent market data rows from the database."""
        result = await db.execute(
            select(MarketData)
            .where(MarketData.ticker_symbol == ticker)
            .order_by(MarketData.date.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "date": str(r.date),
                "open": float(r.open_price) if r.open_price else None,
                "close": float(r.close_price) if r.close_price else None,
                "high": float(r.high_price) if r.high_price else None,
                "low": float(r.low_price) if r.low_price else None,
                "volume": r.volume,
            }
            for r in rows
        ]
