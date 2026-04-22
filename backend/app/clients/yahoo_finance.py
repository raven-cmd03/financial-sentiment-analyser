import logging
from datetime import datetime, timezone

import yfinance

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class YahooFinanceClient(BaseAPIClient):
    """Fetches financial news for a ticker via the yfinance library."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def fetch_news(self, query: str, max_results: int = 10) -> list[dict]:
        """Fetch news for a ticker symbol using yfinance.

        ``query`` is treated as a ticker symbol (e.g. "AAPL").
        """
        logger.info("Fetching Yahoo Finance news for ticker=%r", query)
        ticker = yfinance.Ticker(query)

        try:
            raw_news = ticker.news or []
        except Exception as exc:
            logger.error("yfinance news fetch failed: %s", exc)
            return []

        articles: list[dict] = []
        for item in raw_news[:max_results]:
            articles.append(self._normalize(item))

        logger.info("Retrieved %d articles from Yahoo Finance", len(articles))
        return articles

    @staticmethod
    def _normalize(item: dict) -> dict:
        pub_timestamp = item.get("providerPublishTime")
        pub_date = (
            datetime.fromtimestamp(pub_timestamp, tz=timezone.utc).isoformat()
            if pub_timestamp
            else None
        )
        return {
            "title": item.get("title", ""),
            "content": item.get("summary", item.get("title", "")),
            "source": item.get("publisher", "Yahoo Finance"),
            "url": item.get("link", ""),
            "publication_date": pub_date,
        }
