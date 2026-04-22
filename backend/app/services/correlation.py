import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correlation import Correlation
from app.models.market_data import MarketData
from app.models.sentiment_result import SentimentResult
from app.models.news_article import NewsArticle, ArticleCompany
from app.models.company import Company

logger = logging.getLogger(__name__)


class CorrelationCalculator:
    # ------------------------------------------------------------------
    # Core statistical methods
    # ------------------------------------------------------------------

    @staticmethod
    def pearson_correlation(
        x: np.ndarray | list, y: np.ndarray | list
    ) -> tuple[float, float]:
        """Return (r, p_value) using Pearson product-moment correlation."""
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        r, p = stats.pearsonr(x, y)
        return float(r), float(p)

    @staticmethod
    def spearman_correlation(
        x: np.ndarray | list, y: np.ndarray | list
    ) -> tuple[float, float]:
        """Return (rho, p_value) using Spearman rank correlation."""
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        rho, p = stats.spearmanr(x, y)
        return float(rho), float(p)

    @staticmethod
    def time_lagged_correlation(
        sentiment: np.ndarray | list,
        prices: np.ndarray | list,
        lag: int,
    ) -> tuple[float, float]:
        """Align sentiment and price series with a time lag, then compute Pearson r.

        A positive lag means sentiment leads prices (sentiment[:-lag] vs prices[lag:]).
        """
        sentiment = np.asarray(sentiment, dtype=float)
        prices = np.asarray(prices, dtype=float)

        if lag > 0:
            s = sentiment[:-lag]
            p = prices[lag:]
        elif lag < 0:
            s = sentiment[-lag:]
            p = prices[:lag]
        else:
            s, p = sentiment, prices

        if len(s) < 3:
            return 0.0, 1.0

        r, pval = stats.pearsonr(s, p)
        return float(r), float(pval)

    @staticmethod
    def rolling_correlation(
        x: np.ndarray | list,
        y: np.ndarray | list,
        window: int,
    ) -> list[float]:
        """Compute a sliding-window Pearson r over aligned series."""
        sx = pd.Series(np.asarray(x, dtype=float))
        sy = pd.Series(np.asarray(y, dtype=float))
        rolling = sx.rolling(window).corr(sy)
        return [round(v, 4) if not np.isnan(v) else None for v in rolling]

    # ------------------------------------------------------------------
    # End-to-end DB workflow
    # ------------------------------------------------------------------

    async def compute_all_correlations(
        self,
        ticker: str,
        db: AsyncSession,
        days: int = 30,
    ) -> list[dict]:
        """Fetch sentiment + price data, calculate all correlation types,
        and persist results to the correlations table."""
        sentiment_series, price_series = await self._load_aligned_data(
            ticker, db, days
        )

        if len(sentiment_series) < 5:
            logger.warning(
                "Not enough data points (%d) for %s correlations",
                len(sentiment_series),
                ticker,
            )
            return []

        results: list[dict] = []

        r, p = self.pearson_correlation(sentiment_series, price_series)
        results.append(self._build_record(ticker, "pearson", r, p, len(sentiment_series)))

        rho, p = self.spearman_correlation(sentiment_series, price_series)
        results.append(self._build_record(ticker, "spearman", rho, p, len(sentiment_series)))

        for lag in (1, 3, 5):
            r, p = self.time_lagged_correlation(sentiment_series, price_series, lag)
            rec = self._build_record(ticker, "time_lagged", r, p, len(sentiment_series))
            rec["time_lag"] = lag
            results.append(rec)

        rolling = self.rolling_correlation(sentiment_series, price_series, window=7)
        valid_vals = [v for v in rolling if v is not None]
        if valid_vals:
            avg_r = float(np.mean(valid_vals))
            results.append(
                self._build_record(ticker, "rolling_7d", avg_r, None, len(valid_vals))
            )

        for rec in results:
            corr = Correlation(
                ticker_symbol=rec["ticker_symbol"],
                correlation_type=rec["correlation_type"],
                correlation_value=rec["correlation_value"],
                p_value=rec.get("p_value"),
                sample_size=rec.get("sample_size"),
                time_lag=rec.get("time_lag"),
            )
            db.add(corr)

        try:
            await db.flush()
            logger.info("Stored %d correlation records for %s", len(results), ticker)
        except Exception:
            logger.exception("Failed to store correlations for %s", ticker)
            raise

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_record(
        ticker: str,
        corr_type: str,
        value: float,
        p_value: float | None,
        sample_size: int,
    ) -> dict:
        return {
            "ticker_symbol": ticker,
            "correlation_type": corr_type,
            "correlation_value": round(value, 4),
            "p_value": round(p_value, 8) if p_value is not None else None,
            "sample_size": sample_size,
            "time_lag": None,
        }

    async def _load_aligned_data(
        self, ticker: str, db: AsyncSession, days: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Load daily-average sentiment scores and daily price changes,
        aligned by date."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Daily avg sentiment (positive - negative) for this ticker only.
        # Bucketed by NewsArticle.publication_date so backfills don't
        # collapse thousands of historical articles onto the day they
        # were scored — see the matching fix in api/companies.py.
        sent_q = (
            select(
                func.date(NewsArticle.publication_date).label("day"),
                func.avg(SentimentResult.positive_score - SentimentResult.negative_score).label("score"),
            )
            .join(NewsArticle, SentimentResult.article_id == NewsArticle.article_id)
            .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
            .join(Company, Company.company_id == ArticleCompany.company_id)
            .where(
                Company.ticker_symbol == ticker,
                NewsArticle.publication_date >= cutoff,
            )
            .group_by(func.date(NewsArticle.publication_date))
            .order_by(func.date(NewsArticle.publication_date))
        )
        sent_rows = (await db.execute(sent_q)).all()
        sent_df = pd.DataFrame(sent_rows, columns=["day", "score"])

        # Daily close-to-close price change
        price_q = (
            select(MarketData.date, MarketData.close_price)
            .where(
                MarketData.ticker_symbol == ticker,
                MarketData.date >= cutoff.date(),
            )
            .order_by(MarketData.date)
        )
        price_rows = (await db.execute(price_q)).all()
        price_df = pd.DataFrame(price_rows, columns=["day", "close"])
        price_df["day"] = pd.to_datetime(price_df["day"])
        price_df["change"] = price_df["close"].astype(float).pct_change()

        sent_df["day"] = pd.to_datetime(sent_df["day"])
        merged = pd.merge(sent_df, price_df[["day", "change"]], on="day").dropna()

        return (
            merged["score"].to_numpy(dtype=float),
            merged["change"].to_numpy(dtype=float),
        )
