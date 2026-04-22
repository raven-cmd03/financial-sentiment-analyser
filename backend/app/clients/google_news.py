import logging
from datetime import datetime
from urllib.parse import quote_plus

import feedparser

from .base import BaseAPIClient

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q={query}+stock+market&hl=en-US&gl=US&ceid=US:en"
)


class GoogleNewsClient(BaseAPIClient):
    """Fetches financial news from Google News RSS feeds."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    async def fetch_news(self, query: str, max_results: int = 10) -> list[dict]:
        url = _GOOGLE_NEWS_RSS.format(query=quote_plus(query))
        logger.info("Fetching Google News RSS for query=%r", query)

        response = await self._request("GET", url)
        feed = feedparser.parse(response.text)

        articles: list[dict] = []
        for entry in feed.entries[:max_results]:
            pub_date = self._parse_date(entry.get("published"))
            articles.append(
                {
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", ""),
                    "source": entry.get("source", {}).get("title", "Google News"),
                    "url": entry.get("link", ""),
                    "publication_date": pub_date,
                }
            )

        logger.info("Retrieved %d articles from Google News", len(articles))
        return articles

    @staticmethod
    def _parse_date(date_str: str | None) -> str | None:
        if not date_str:
            return None
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str).isoformat()
        except (ValueError, TypeError):
            return date_str
