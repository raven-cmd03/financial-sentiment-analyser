"""Alpha Vantage async client.

Provides two capabilities the rest of the system consumes:

1. ``fetch_news(query)`` — news articles from the ``NEWS_SENTIMENT`` endpoint,
   normalized into the same shape as the Google News / Yahoo Finance clients so
   it can drop into the existing ingestion pipeline.
2. ``fetch_daily_prices(ticker)`` — OHLCV rows from ``TIME_SERIES_DAILY``,
   returned as a ``pandas.DataFrame`` that matches what
   ``MarketDataService.store_market_data`` already expects. This is how we
   satisfy FR-05 (real-time + historical market data) and wire a real price
   signal into the correlation engine.

Free tier quotas (5 requests/minute, 500/day) are enforced via the base class's
token-bucket rate limiter.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .base import BaseAPIClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.alphavantage.co/query"

# Alpha Vantage returns its own sentiment labels — map them onto our 3-class
# positive/neutral/negative schema so the frontend can render them consistently
# (we still rerun FinBERT server-side; these are used only as metadata).
_AV_SENTIMENT_MAP = {
    "bearish": "negative",
    "somewhat-bearish": "negative",
    "neutral": "neutral",
    "somewhat_bullish": "positive",
    "somewhat-bullish": "positive",
    "bullish": "positive",
}


class AlphaVantageError(RuntimeError):
    """Raised when Alpha Vantage returns a structured error payload."""


class AlphaVantageClient(BaseAPIClient):
    """Async Alpha Vantage client with resilience patterns."""

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        # Free tier: 5 requests/minute. Give ourselves headroom by defaulting
        # the bucket to 4/minute so bursts don't trip the quota.
        kwargs.setdefault("rate_limit", 4.0)
        kwargs.setdefault("rate_period", 60.0)
        super().__init__(**kwargs)
        if not api_key:
            raise ValueError("AlphaVantageClient requires an api_key")
        self._api_key = api_key

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    async def fetch_news(
        self,
        query: str,
        max_results: int = 10,
        *,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        sort: str = "LATEST",
        raise_on_rate_limit: bool = False,
    ) -> list[dict]:
        """Return normalized news articles for a ticker via NEWS_SENTIMENT.

        ``query`` is treated as a ticker symbol (e.g. ``"AAPL"``). If the
        upstream call fails or returns an error object, we return ``[]`` so the
        ingestion pipeline continues with other sources — Alpha Vantage must
        never be able to take news collection down.

        Historical backfill: pass ``time_from`` / ``time_to`` (datetimes, UTC)
        to scope the search to a window. Alpha Vantage's hard per-call ceiling
        is 1000 articles, so for long spans the caller should chunk into
        monthly-ish windows. When both bounds are provided, ``sort="EARLIEST"``
        is often more useful for pagination.
        """
        limit = max(1, min(max_results, 1000))
        params: dict[str, Any] = {
            "function": "NEWS_SENTIMENT",
            "tickers": query.upper(),
            "limit": limit,
            "sort": sort,
            "apikey": self._api_key,
        }
        if time_from is not None:
            params["time_from"] = _format_av_window(time_from)
        if time_to is not None:
            params["time_to"] = _format_av_window(time_to)

        logger.info(
            "Fetching Alpha Vantage news ticker=%r time_from=%s time_to=%s limit=%d",
            query,
            params.get("time_from"),
            params.get("time_to"),
            limit,
        )

        try:
            response = await self._request("GET", _BASE_URL, params=params)
            payload = response.json()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Alpha Vantage news request failed: %s", exc)
            return []

        if raise_on_rate_limit and isinstance(payload, dict):
            throttle_msg = payload.get("Note") or payload.get("Information")
            if throttle_msg:
                raise AlphaVantageError(str(throttle_msg))

        articles = self._parse_news_payload(payload, ticker=query.upper())
        logger.info("Retrieved %d articles from Alpha Vantage", len(articles))
        return articles[:limit]

    @staticmethod
    def _parse_news_payload(payload: dict, *, ticker: str) -> list[dict]:
        if not isinstance(payload, dict):
            return []

        if "Note" in payload or "Information" in payload:
            logger.warning(
                "Alpha Vantage rate-limited or informational response: %s",
                payload.get("Note") or payload.get("Information"),
            )
            return []
        if "Error Message" in payload:
            logger.warning(
                "Alpha Vantage returned error: %s", payload["Error Message"]
            )
            return []

        feed = payload.get("feed") or []
        out: list[dict] = []
        for item in feed:
            pub_raw = item.get("time_published")
            pub_iso = _parse_av_timestamp(pub_raw)

            av_label = (item.get("overall_sentiment_label") or "").lower()
            av_score = _safe_float(item.get("overall_sentiment_score"))
            ticker_label, ticker_score = _extract_ticker_sentiment(
                item.get("ticker_sentiment"), ticker
            )

            # Prefer the per-ticker sentiment (scoped to the queried symbol);
            # fall back to the article's overall sentiment.
            mapped_label = (
                _AV_SENTIMENT_MAP.get(ticker_label)
                or _AV_SENTIMENT_MAP.get(av_label)
            )
            mapped_score = ticker_score if ticker_score is not None else av_score

            source = item.get("source") or item.get("source_domain") or "Alpha Vantage"
            summary = item.get("summary") or item.get("title") or ""

            out.append(
                {
                    "title": item.get("title", ""),
                    "content": summary,
                    "source": source,
                    "url": item.get("url", ""),
                    "publication_date": pub_iso,
                    "provider_sentiment": {
                        "label": mapped_label,
                        "score": mapped_score,
                        "source": "alpha_vantage",
                    }
                    if mapped_label
                    else None,
                }
            )
        return out

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def fetch_daily_prices(
        self, ticker: str, outputsize: str = "compact"
    ) -> pd.DataFrame:
        """Return a DataFrame of daily OHLCV rows for ``ticker``.

        ``outputsize="compact"`` returns the last ~100 trading days (free tier
        friendly and plenty for 30-day correlations). ``"full"`` returns the
        full 20+ year history but is rate-limit-expensive.

        The returned frame uses our canonical column names:
        ``open_price, high_price, low_price, close_price, volume`` with a
        ``DatetimeIndex`` — identical to ``MarketDataService.fetch_stock_data``
        so the existing upsert path just works.
        """
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker.upper(),
            "outputsize": outputsize,
            "datatype": "json",
            "apikey": self._api_key,
        }
        logger.info("Fetching Alpha Vantage daily prices for %s", ticker)

        response = await self._request("GET", _BASE_URL, params=params)
        payload = response.json()
        return self._parse_price_payload(payload, ticker=ticker.upper())

    @staticmethod
    def _parse_price_payload(payload: dict, *, ticker: str) -> pd.DataFrame:
        if not isinstance(payload, dict):
            raise AlphaVantageError(f"Unexpected Alpha Vantage response for {ticker}")
        if "Note" in payload or "Information" in payload:
            # Free-tier throttling; bubble up so the caller can fall back.
            raise AlphaVantageError(
                payload.get("Note") or payload["Information"]
            )
        if "Error Message" in payload:
            raise AlphaVantageError(payload["Error Message"])

        series = payload.get("Time Series (Daily)") or {}
        if not series:
            return pd.DataFrame(
                columns=[
                    "open_price",
                    "high_price",
                    "low_price",
                    "close_price",
                    "volume",
                ]
            )

        rows: list[dict] = []
        index: list[pd.Timestamp] = []
        for date_str, ohlcv in series.items():
            try:
                # Parse the whole row FIRST so a bad value doesn't leave
                # ``index`` and ``rows`` out of sync.
                parsed_row = {
                    "open_price": float(ohlcv.get("1. open", 0.0)),
                    "high_price": float(ohlcv.get("2. high", 0.0)),
                    "low_price": float(ohlcv.get("3. low", 0.0)),
                    "close_price": float(ohlcv.get("4. close", 0.0)),
                    "volume": int(float(ohlcv.get("5. volume", 0))),
                }
                parsed_ts = pd.Timestamp(date_str)
            except (TypeError, ValueError) as exc:
                logger.debug("Skipping malformed AV row %s: %s", date_str, exc)
                continue
            index.append(parsed_ts)
            rows.append(parsed_row)

        df = pd.DataFrame(rows, index=pd.DatetimeIndex(index))
        df = df.sort_index()
        return df


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _format_av_window(dt: datetime) -> str:
    """Format a datetime as Alpha Vantage's NEWS_SENTIMENT window timestamp.

    AV expects ``YYYYMMDDTHHMM`` in UTC. Naive datetimes are assumed UTC;
    aware datetimes are converted.
    """
    if dt.tzinfo is None:
        aware = dt.replace(tzinfo=timezone.utc)
    else:
        aware = dt.astimezone(timezone.utc)
    return aware.strftime("%Y%m%dT%H%M")


def _parse_av_timestamp(raw: str | None) -> str | None:
    """Alpha Vantage formats timestamps as ``YYYYMMDDTHHMMSS`` in UTC."""
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(raw).isoformat()
        except (ValueError, TypeError):
            return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_ticker_sentiment(
    ticker_sentiment: Any, ticker: str
) -> tuple[str | None, float | None]:
    if not isinstance(ticker_sentiment, list):
        return None, None
    ticker_upper = ticker.upper()
    for entry in ticker_sentiment:
        if not isinstance(entry, dict):
            continue
        if (entry.get("ticker") or "").upper() == ticker_upper:
            label = (entry.get("ticker_sentiment_label") or "").lower()
            score = _safe_float(entry.get("ticker_sentiment_score"))
            return label or None, score
    return None, None
