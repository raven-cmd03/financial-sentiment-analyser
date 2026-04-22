"""GDELT DOC 2.0 async client.

GDELT (https://www.gdeltproject.org/) provides a free, no-API-key news
archive that goes back to February 2015 and covers ~100 000 news sites
worldwide in 65 languages. The DOC 2.0 ``/api/v2/doc/doc`` endpoint
accepts a keyword query plus ``startdatetime`` / ``enddatetime`` and
returns up to 250 article metadata records per call, making it an ideal
free alternative to Alpha Vantage for historical news backfill.

We normalize the payload into the same ``{title, content, source, url,
publication_date}`` shape that the rest of the ingestion pipeline
consumes, so GDELT articles land in the DB through exactly the same
upsert path as Google News, Yahoo, or Alpha Vantage.

Notes on the free API:

* No authentication required.
* GDELT does not publish an official rate limit, but prolonged 2–3
  req/sec is safe. We default the token bucket to 2 req/sec which is
  conservative and keeps us well inside any implicit cap.
* GDELT returns article *metadata* only (title, URL, domain, tone).
  The ``content`` field is therefore left empty; FinBERT will run on
  the title alone, which is already the fallback behaviour elsewhere
  (``analyze_sentiment_task`` handles empty content).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from .base import BaseAPIClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT caps each artlist response at 250 records.
_MAX_RECORDS_PER_CALL = 250

# GDELT's edge layer silently drops requests from the default
# ``python-httpx`` User-Agent (returns an empty body / connection reset
# depending on origin). A plain browser UA is sufficient.
_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; financial-sentiment-analyzer/1.0; "
    "+https://github.com/)"
)


def _format_gdelt_datetime(dt: datetime) -> str:
    """GDELT wants ``YYYYMMDDHHMMSS`` in UTC."""
    if dt.tzinfo is None:
        aware = dt.replace(tzinfo=timezone.utc)
    else:
        aware = dt.astimezone(timezone.utc)
    return aware.strftime("%Y%m%d%H%M%S")


def _parse_gdelt_seendate(raw: str | None) -> str | None:
    """GDELT emits ``seendate`` as ``YYYYMMDDTHHMMSSZ``."""
    if not raw:
        return None
    try:
        cleaned = raw.replace("Z", "").replace("T", "")
        dt = datetime.strptime(cleaned, "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
        return dt.isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(raw).isoformat()
        except (ValueError, TypeError):
            return None


def _build_query(query: str, english_only: bool) -> str:
    """Wrap the user query with GDELT operators.

    We always request English-language sources because FinBERT is
    English-only. GDELT also requires any query containing ``OR`` to be
    enclosed in parentheses, so we wrap unparenthesised compound queries
    automatically.
    """
    core = query.strip()
    # GDELT rejects bare ``OR`` queries with:
    #   "Queries containing OR'd terms must be surrounded by ()."
    # Detect OR as a whole word and wrap if the caller hasn't already.
    if re.search(r"\bOR\b", core) and not (
        core.startswith("(") and core.endswith(")")
    ):
        core = f"({core})"

    parts: list[str] = [core]
    if english_only and "sourcelang:" not in core.lower():
        parts.append("sourcelang:english")
    return " ".join(parts)


class GdeltClient(BaseAPIClient):
    """Async client for GDELT DOC 2.0 article-list search."""

    def __init__(self, **kwargs: Any) -> None:
        # Conservative defaults — GDELT has no published rate limit but
        # returns 429 aggressively at anything above ~1 req / 5 s. We
        # configure 1 token every 5 seconds by default. The endpoint
        # is also notoriously slow (10-60s per call under load), so we
        # give it a 60s timeout instead of the base 30s.
        kwargs.setdefault("rate_limit", 1.0)
        kwargs.setdefault("rate_period", 5.0)
        kwargs.setdefault("timeout", 60.0)
        super().__init__(**kwargs)

    async def fetch_news(
        self,
        query: str,
        max_results: int = 250,
        *,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        sort: str = "DateDesc",
        english_only: bool = True,
    ) -> list[dict]:
        """Return normalized articles for ``query`` within the time window.

        ``query`` is passed through to GDELT largely as-is. For tickers,
        pass something like ``'AAPL OR "Apple Inc"'`` to get both
        headline variants. ``time_from`` / ``time_to`` default to
        "unbounded" when omitted, but you almost always want to pass
        them during a backfill so the window matches the iteration step.
        """
        limit = max(1, min(max_results, _MAX_RECORDS_PER_CALL))
        params: dict[str, Any] = {
            "query": _build_query(query, english_only=english_only),
            "mode": "artlist",
            "format": "json",
            "maxrecords": limit,
            "sort": sort,
        }
        if time_from is not None:
            params["startdatetime"] = _format_gdelt_datetime(time_from)
        if time_to is not None:
            params["enddatetime"] = _format_gdelt_datetime(time_to)

        logger.info(
            "GDELT query=%r start=%s end=%s limit=%d",
            params["query"],
            params.get("startdatetime"),
            params.get("enddatetime"),
            limit,
        )

        try:
            response = await self._request(
                "GET",
                _BASE_URL,
                params=params,
                headers={"User-Agent": _DEFAULT_UA},
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("GDELT request failed: %s", exc)
            return []

        # GDELT occasionally returns an HTML error page with 200 status
        # when overloaded. Guard the JSON decode so we degrade to [].
        try:
            payload = response.json()
        except Exception as exc:
            logger.warning("GDELT returned non-JSON payload: %s", exc)
            return []

        articles = self._parse_articles(payload)
        logger.info("Retrieved %d articles from GDELT", len(articles))
        return articles

    @staticmethod
    def _parse_articles(payload: dict) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        feed = payload.get("articles") or []
        out: list[dict] = []
        for item in feed:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            if not url or not title:
                continue

            out.append(
                {
                    "title": title,
                    # GDELT DOC 2.0 exposes metadata only, not article
                    # body. Callers that want full text must fetch the
                    # URL themselves. Empty content is fine: FinBERT
                    # scores on title alone in that case.
                    "content": "",
                    "source": (
                        item.get("domain")
                        or item.get("sourcecountry")
                        or "GDELT"
                    )[:100],
                    "url": url,
                    "publication_date": _parse_gdelt_seendate(
                        item.get("seendate")
                    ),
                }
            )
        return out
