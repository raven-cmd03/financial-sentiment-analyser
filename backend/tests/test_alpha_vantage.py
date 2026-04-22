"""Unit tests for the Alpha Vantage client's payload parsers.

These are pure parsing tests against fixture payloads that match the real
Alpha Vantage response shapes — no network calls. They guard the news
ingestion pipeline and the correlation-engine price feed against upstream
schema drift and against our own regressions.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.clients.alpha_vantage import AlphaVantageClient, AlphaVantageError


# ---------------------------------------------------------------------------
# NEWS_SENTIMENT
# ---------------------------------------------------------------------------


def _news_fixture() -> dict:
    return {
        "items": "2",
        "sentiment_score_definition": "...",
        "feed": [
            {
                "title": "Apple beats earnings expectations",
                "url": "https://example.com/aapl-earnings",
                "time_published": "20250115T131500",
                "summary": "Apple posted record revenue this quarter.",
                "source": "Example Wire",
                "source_domain": "example.com",
                "overall_sentiment_score": 0.42,
                "overall_sentiment_label": "Somewhat-Bullish",
                "ticker_sentiment": [
                    {
                        "ticker": "AAPL",
                        "ticker_sentiment_score": "0.51",
                        "ticker_sentiment_label": "Bullish",
                    },
                    {
                        "ticker": "MSFT",
                        "ticker_sentiment_score": "0.0",
                        "ticker_sentiment_label": "Neutral",
                    },
                ],
            },
            {
                "title": "Concerns mount over iPhone demand",
                "url": "https://example.com/aapl-demand",
                "time_published": "20250114T200000",
                "summary": "Analysts see weakening demand.",
                "source": "Another Wire",
                "overall_sentiment_score": -0.18,
                "overall_sentiment_label": "Somewhat-Bearish",
                # Note: no ticker_sentiment — forces fallback to overall.
            },
        ],
    }


def test_parse_news_payload_normalizes_feed_items() -> None:
    articles = AlphaVantageClient._parse_news_payload(
        _news_fixture(), ticker="AAPL"
    )
    assert len(articles) == 2

    a, b = articles
    assert a["title"] == "Apple beats earnings expectations"
    assert a["source"] == "Example Wire"
    assert a["url"] == "https://example.com/aapl-earnings"
    # 20250115T131500 → ISO 8601 UTC
    assert a["publication_date"].startswith("2025-01-15T13:15:00")
    # Per-ticker label wins when present.
    assert a["provider_sentiment"]["label"] == "positive"
    assert a["provider_sentiment"]["score"] == pytest.approx(0.51)

    # Falls back to the overall sentiment when ticker_sentiment is missing.
    assert b["provider_sentiment"]["label"] == "negative"
    assert b["provider_sentiment"]["score"] == pytest.approx(-0.18)


def test_parse_news_payload_handles_rate_limit_note() -> None:
    payload = {"Note": "Thank you for using Alpha Vantage! ..."}
    assert AlphaVantageClient._parse_news_payload(payload, ticker="AAPL") == []


def test_parse_news_payload_handles_error_message() -> None:
    payload = {"Error Message": "Invalid API call."}
    assert AlphaVantageClient._parse_news_payload(payload, ticker="AAPL") == []


def test_parse_news_payload_handles_empty_feed() -> None:
    assert AlphaVantageClient._parse_news_payload({"feed": []}, ticker="AAPL") == []
    assert AlphaVantageClient._parse_news_payload({}, ticker="AAPL") == []


# ---------------------------------------------------------------------------
# TIME_SERIES_DAILY
# ---------------------------------------------------------------------------


def _prices_fixture() -> dict:
    return {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2025-01-15": {
                "1. open": "230.10",
                "2. high": "232.00",
                "3. low": "229.00",
                "4. close": "231.45",
                "5. volume": "51234000",
            },
            "2025-01-14": {
                "1. open": "228.90",
                "2. high": "230.30",
                "3. low": "227.75",
                "4. close": "230.00",
                "5. volume": "48112200",
            },
        },
    }


def test_parse_price_payload_returns_canonical_dataframe() -> None:
    df = AlphaVantageClient._parse_price_payload(_prices_fixture(), ticker="AAPL")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    ]
    # Sorted ascending by date.
    assert df.index.is_monotonic_increasing
    assert df.loc[pd.Timestamp("2025-01-15"), "close_price"] == pytest.approx(231.45)
    assert df.loc[pd.Timestamp("2025-01-14"), "volume"] == 48112200


def test_parse_price_payload_raises_on_rate_limit() -> None:
    with pytest.raises(AlphaVantageError):
        AlphaVantageClient._parse_price_payload(
            {"Note": "rate-limited"}, ticker="AAPL"
        )


def test_parse_price_payload_returns_empty_dataframe_for_empty_series() -> None:
    df = AlphaVantageClient._parse_price_payload(
        {"Time Series (Daily)": {}}, ticker="AAPL"
    )
    assert df.empty
    assert list(df.columns) == [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    ]


def test_parse_price_payload_skips_malformed_rows() -> None:
    payload = {
        "Time Series (Daily)": {
            "2025-01-15": {
                "1. open": "not-a-float",
                "2. high": "232.00",
                "3. low": "229.00",
                "4. close": "231.45",
                "5. volume": "51234000",
            },
            "2025-01-14": {
                "1. open": "228.90",
                "2. high": "230.30",
                "3. low": "227.75",
                "4. close": "230.00",
                "5. volume": "48112200",
            },
        }
    }
    df = AlphaVantageClient._parse_price_payload(payload, ticker="AAPL")
    # Malformed row dropped, good row retained.
    assert len(df) == 1
    assert df.index[0] == pd.Timestamp("2025-01-14")


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def test_client_requires_api_key() -> None:
    with pytest.raises(ValueError):
        AlphaVantageClient(api_key="")
