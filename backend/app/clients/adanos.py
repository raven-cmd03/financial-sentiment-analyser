import logging

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.adanos.org/v1"
_FREE_TIER_MONTHLY_LIMIT = 250


class AdanosClient:
    """Client for the Adanos X Stock Sentiment API.

    This does NOT inherit from BaseAPIClient because it serves a different
    purpose (sentiment scores rather than news articles).
    """

    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )
        self._request_count = 0

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _check_rate_limit(self) -> None:
        if self._request_count >= _FREE_TIER_MONTHLY_LIMIT:
            raise RuntimeError(
                f"Adanos free-tier monthly limit reached ({_FREE_TIER_MONTHLY_LIMIT} requests)"
            )

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        self._check_rate_limit()
        logger.debug("Adanos %s %s", method.upper(), path)

        response = await self._client.request(method, path, **kwargs)
        response.raise_for_status()
        self._request_count += 1
        return response

    async def get_sentiment(self, ticker: str) -> dict:
        """Return sentiment metrics for a single ticker.

        Returns dict with keys: buzz_score, bullish_ratio, bearish_ratio,
        post_volume, sentiment_trend.
        """
        logger.info("Fetching Adanos sentiment for ticker=%r", ticker)
        response = await self._request("GET", f"/sentiment/{ticker}")
        data = response.json()

        return {
            "buzz_score": data.get("buzz_score"),
            "bullish_ratio": data.get("bullish_ratio"),
            "bearish_ratio": data.get("bearish_ratio"),
            "post_volume": data.get("post_volume"),
            "sentiment_trend": data.get("sentiment_trend"),
        }

    async def get_trending(self) -> list[dict]:
        """Return a list of currently trending tickers with sentiment data."""
        logger.info("Fetching Adanos trending tickers")
        response = await self._request("GET", "/trending")
        data = response.json()

        if isinstance(data, list):
            return data
        return data.get("tickers", data.get("results", []))
