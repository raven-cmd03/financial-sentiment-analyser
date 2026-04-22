"""Unit tests for the GDELT DOC 2.0 async client.

These cover the request plumbing (time-window formatting, English-only
query augmentation, maxrecords clamp) and the payload parser. They use
the same stubbing pattern as ``test_backfill.py`` — no network calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.clients.gdelt import (
    GdeltClient,
    _build_query,
    _format_gdelt_datetime,
    _parse_gdelt_seendate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_format_gdelt_datetime_naive_is_treated_as_utc() -> None:
    assert (
        _format_gdelt_datetime(datetime(2024, 6, 15, 13, 45, 30))
        == "20240615134530"
    )


def test_format_gdelt_datetime_aware_converts_to_utc() -> None:
    tz = timezone(timedelta(hours=5))
    dt = datetime(2024, 6, 15, 13, 45, 30, tzinfo=tz)
    # 13:45:30 in UTC+5 == 08:45:30 UTC
    assert _format_gdelt_datetime(dt) == "20240615084530"


def test_parse_gdelt_seendate_canonical() -> None:
    assert (
        _parse_gdelt_seendate("20231115T120000Z")
        == "2023-11-15T12:00:00+00:00"
    )


def test_parse_gdelt_seendate_bad_value_returns_none() -> None:
    assert _parse_gdelt_seendate("") is None
    assert _parse_gdelt_seendate(None) is None
    assert _parse_gdelt_seendate("not-a-date") is None


def test_build_query_adds_english_filter() -> None:
    assert _build_query("AAPL", english_only=True) == "AAPL sourcelang:english"


def test_build_query_respects_existing_lang_filter() -> None:
    q = _build_query("AAPL sourcelang:english", english_only=True)
    # Should not double-append.
    assert q.lower().count("sourcelang:") == 1


def test_build_query_can_skip_english_filter() -> None:
    assert _build_query("AAPL", english_only=False) == "AAPL"


def test_build_query_wraps_or_terms_in_parens() -> None:
    # GDELT returns 400 otherwise: "Queries containing OR'd terms must
    # be surrounded by ()."
    q = _build_query('AAPL OR "Apple Inc"', english_only=True)
    assert q.startswith('(AAPL OR "Apple Inc")')
    assert q.endswith("sourcelang:english")


def test_build_query_does_not_double_wrap_parens() -> None:
    q = _build_query('(AAPL OR "Apple Inc")', english_only=False)
    assert q == '(AAPL OR "Apple Inc")'


# ---------------------------------------------------------------------------
# fetch_news
# ---------------------------------------------------------------------------


class _StubResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.text = ""

    def json(self) -> dict:
        return self._payload


async def test_fetch_news_forwards_window_and_clamps_limit() -> None:
    async with GdeltClient() as client:
        captured: dict = {}

        async def fake_request(method, url, *, params=None, **_kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["params"] = params
            return _StubResponse({"articles": []})

        client._request = fake_request  # type: ignore[assignment]

        await client.fetch_news(
            'AAPL OR "Apple Inc"',
            max_results=500,
            time_from=datetime(2023, 1, 1),
            time_to=datetime(2023, 2, 1),
        )

    # English-only filter gets added by default.
    assert "sourcelang:english" in captured["params"]["query"]
    # GDELT hard cap is 250.
    assert captured["params"]["maxrecords"] == 250
    assert captured["params"]["startdatetime"] == "20230101000000"
    assert captured["params"]["enddatetime"] == "20230201000000"
    assert captured["params"]["mode"] == "artlist"
    assert captured["params"]["format"] == "json"


async def test_fetch_news_parses_articles() -> None:
    payload = {
        "articles": [
            {
                "url": "https://example.com/a1",
                "title": "Apple posts record revenue",
                "seendate": "20231115T120000Z",
                "domain": "example.com",
                "language": "English",
                "sourcecountry": "United States",
            },
            {
                "url": "https://example.com/a2",
                "title": "Supply chain concerns",
                "seendate": "20231116T080000Z",
                "domain": "another.com",
            },
            # Rejected: missing URL.
            {"title": "Orphan", "seendate": "20231117T000000Z"},
            # Rejected: missing title.
            {"url": "https://example.com/a3", "seendate": "20231118T000000Z"},
        ]
    }
    articles = GdeltClient._parse_articles(payload)

    assert len(articles) == 2
    a1 = articles[0]
    assert a1["url"] == "https://example.com/a1"
    assert a1["title"] == "Apple posts record revenue"
    assert a1["source"] == "example.com"
    assert a1["content"] == ""  # GDELT is metadata-only
    assert a1["publication_date"] == "2023-11-15T12:00:00+00:00"


class _BadJsonResponse:
    text = "<html>overloaded</html>"

    def json(self):
        raise ValueError("not json")


async def test_fetch_news_handles_non_json_payload() -> None:
    """GDELT occasionally returns HTML error pages with a 200 status."""
    async with GdeltClient() as client:
        async def fake_request(method, url, *, params=None, **_kwargs):
            return _BadJsonResponse()

        client._request = fake_request  # type: ignore[assignment]

        # Should degrade to [] rather than raise.
        articles = await client.fetch_news("AAPL")
        assert articles == []


async def test_fetch_news_empty_articles_list() -> None:
    async with GdeltClient() as client:
        async def fake_request(method, url, *, params=None, **_kwargs):
            return _StubResponse({"articles": []})

        client._request = fake_request  # type: ignore[assignment]
        assert await client.fetch_news("AAPL") == []
