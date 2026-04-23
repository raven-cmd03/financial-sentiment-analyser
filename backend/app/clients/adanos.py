import logging

import httpx

logger = logging.getLogger(__name__)

# Adanos restructured their API surface around v1.28.0: the old flat
# ``/v1/sentiment/{ticker}`` collapse has been replaced with per-platform
# namespaces. We use the X (Twitter) stocks channel since retail chatter on
# X is the strongest real-time signal for US-listed equities; swap the base
# to ``/reddit/stocks/v1`` or ``/news/stocks/v1`` via ``platform=`` if that
# ever changes.
_BASE_URL = "https://api.adanos.org"
_DEFAULT_PLATFORM = "x/stocks/v1"
_FREE_TIER_MONTHLY_LIMIT = 250


def _normalize_trend(raw: str | None) -> str:
    """Map Adanos' ``rising``/``falling``/``steady`` vocabulary onto the
    ``up``/``down``/``stable`` triad that the rest of the app expects (used
    by the ``TrendIcon`` component, RAG chat context, etc.)."""
    if not raw:
        return "stable"
    lowered = raw.strip().lower()
    if lowered in {"rising", "up", "bullish"}:
        return "up"
    if lowered in {"falling", "down", "bearish"}:
        return "down"
    return "stable"


def _pct_to_ratio(value) -> float | None:
    """Adanos returns bullish/bearish as whole-percent integers (e.g. 71).
    Our DB schema and UI speak in [0, 1] ratios. Convert while tolerating
    ``None`` and already-normalised float inputs (just in case the upstream
    shape changes again)."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    # If the API ever returns the value as a ratio already (e.g. 0.71), keep
    # it as-is; anything > 1 is treated as a percent.
    if f <= 1.0:
        return round(f, 4)
    return round(f / 100.0, 4)


class AdanosClient:
    """Client for the Adanos Market Sentiment API (X / stocks channel).

    Does NOT inherit from ``BaseAPIClient`` — it returns sentiment stats, not
    news articles, so the generic pagination/source-tagging machinery would
    be dead weight here.
    """

    def __init__(
        self,
        api_key: str,
        *,
        platform: str = _DEFAULT_PLATFORM,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._platform = platform.strip("/")
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
                "Adanos free-tier monthly limit reached "
                f"({_FREE_TIER_MONTHLY_LIMIT} requests)"
            )

    async def _request(
        self, method: str, path: str, **kwargs
    ) -> httpx.Response:
        self._check_rate_limit()
        logger.debug("Adanos %s %s", method.upper(), path)

        response = await self._client.request(method, path, **kwargs)
        response.raise_for_status()
        self._request_count += 1
        return response

    async def get_sentiment(self, ticker: str) -> dict:
        """Return sentiment metrics for a single ticker.

        Returns dict with keys: buzz_score, bullish_ratio, bearish_ratio,
        post_volume, sentiment_trend. Returns an empty dict (not a raise)
        when the ticker isn't in Adanos' index so the caller can skip
        persisting the row.
        """
        path = f"/{self._platform}/stock/{ticker}"
        logger.info("Fetching Adanos sentiment for ticker=%r", ticker)
        response = await self._request("GET", path)
        data = response.json()

        if not data.get("found", True):
            logger.info("Adanos has no coverage for %s", ticker)
            return {}

        return {
            "buzz_score": data.get("buzz_score"),
            "bullish_ratio": _pct_to_ratio(data.get("bullish_pct")),
            "bearish_ratio": _pct_to_ratio(data.get("bearish_pct")),
            # ``mentions`` is the total tweet count in the window — this is
            # what the rest of the app calls ``post_volume``.
            "post_volume": data.get("mentions"),
            "sentiment_trend": _normalize_trend(data.get("trend")),
            # Surface the raw composite sentiment too — handy for any caller
            # that wants the -1..+1 score directly without recomputing it
            # from bullish/bearish shares.
            "sentiment_score": data.get("sentiment_score"),
        }

    async def get_trending(self, *, limit: int = 20) -> list[dict]:
        """Return currently trending tickers with sentiment data.

        The new trending endpoint returns ``{"results": [...]}``; each entry
        has the same shape as ``get_sentiment`` plus a ``rank`` field.
        """
        path = f"/{self._platform}/trending"
        logger.info("Fetching Adanos trending tickers (limit=%d)", limit)
        response = await self._request(
            "GET", path, params={"limit": limit}
        )
        data = response.json()

        if isinstance(data, list):
            raw_rows = data
        else:
            raw_rows = data.get("results", data.get("tickers", []))

        normalized: list[dict] = []
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            normalized.append(
                {
                    "ticker": row.get("ticker"),
                    "buzz_score": row.get("buzz_score"),
                    "bullish_ratio": _pct_to_ratio(row.get("bullish_pct")),
                    "bearish_ratio": _pct_to_ratio(row.get("bearish_pct")),
                    "post_volume": row.get("mentions"),
                    "sentiment_trend": _normalize_trend(row.get("trend")),
                    "sentiment_score": row.get("sentiment_score"),
                }
            )
        return normalized
