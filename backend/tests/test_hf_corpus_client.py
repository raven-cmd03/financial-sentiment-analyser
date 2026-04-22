"""Unit tests for the HuggingFace-corpus streaming client.

Focus is on row normalization — the actual ``datasets.load_dataset``
call is skipped (it requires a real HF token + network). The streaming
contract is validated end-to-end in a separate Docker smoke test that
does hit the Hub.
"""

from __future__ import annotations

from datetime import datetime

from app.clients.hf_corpus import (
    HFCorpusClient,
    _extract_tickers,
    _pick_publication_date,
    _pick_source,
    _pick_url,
    _synthetic_url,
)
from app.services.hf_corpus_backfill import _date_in_range


# ---------------------------------------------------------------------------
# _extract_tickers
# ---------------------------------------------------------------------------


def test_extract_tickers_from_stocks_field() -> None:
    extra = {"stocks": ["AAPL", "MSFT"]}
    assert _extract_tickers(extra) == ["AAPL", "MSFT"]


def test_extract_tickers_uppercases_and_strips_dollar_prefix() -> None:
    # sentarl_combined emits "$INDU", "$SPX" for index tickers.
    extra = {"stocks": ["$spx", "$INDU", "aapl"]}
    assert _extract_tickers(extra) == ["SPX", "INDU", "AAPL"]


def test_extract_tickers_merges_stocks_and_mentioned_companies() -> None:
    # Yahoo Finance (felixdrinkall) ships both fields; dedupe without
    # losing order.
    extra = {
        "stocks": ["AAPL", "MSFT"],
        "mentioned_companies": ["MSFT", "GOOGL"],
    }
    assert _extract_tickers(extra) == ["AAPL", "MSFT", "GOOGL"]


def test_extract_tickers_handles_missing_and_malformed() -> None:
    assert _extract_tickers({}) == []
    assert _extract_tickers({"stocks": None}) == []
    assert _extract_tickers({"stocks": "AAPL"}) == []  # string, not list
    assert _extract_tickers({"stocks": [123, None, "AAPL", ""]}) == ["AAPL"]


# ---------------------------------------------------------------------------
# _pick_url / _pick_source / _pick_publication_date / _synthetic_url
# ---------------------------------------------------------------------------


def test_pick_url_priority_order() -> None:
    assert _pick_url({"url": "https://a", "web_url": "https://b"}) == "https://a"
    assert _pick_url({"web_url": "https://b"}) == "https://b"
    assert _pick_url({"link": "https://c"}) == "https://c"
    assert _pick_url({}) == ""
    assert _pick_url({"url": "   "}) == ""


def test_pick_source_prefers_human_readable() -> None:
    assert _pick_source({"source": "Benzinga"}, "fnspid_news") == "Benzinga"
    assert _pick_source({"publisher": "CNBC"}, "cnbc") == "CNBC"
    assert _pick_source({}, "fnspid_news") == "hf:fnspid_news"


def test_pick_publication_date_prefers_trading_anchor() -> None:
    # day-level rows: date is midnight UTC, date_trading is NYSE open.
    raw = {"date": "2023-01-02T00:00:00Z"}
    extra = {"date_trading": "2023-01-03T14:30:00Z"}
    assert _pick_publication_date(raw, extra) == "2023-01-03T14:30:00Z"


def test_pick_publication_date_falls_back_to_top_level() -> None:
    raw = {"date": "2020-06-05T06:30:54Z"}
    assert _pick_publication_date(raw, {}) == "2020-06-05T06:30:54Z"


def test_pick_publication_date_returns_none_when_empty() -> None:
    assert _pick_publication_date({}, {}) is None


def test_synthetic_url_is_stable_and_scheme_qualified() -> None:
    a = _synthetic_url("fnspid_news", "2020-06-05T06:30:54Z", "Some headline")
    b = _synthetic_url("fnspid_news", "2020-06-05T06:30:54Z", "Some headline")
    assert a == b
    assert a.startswith("hf://Brianferrell787/financial-news-multisource/fnspid_news#")


def test_synthetic_url_changes_with_any_input() -> None:
    base = _synthetic_url("fnspid_news", "2020-01-01T00:00:00Z", "Headline A")
    assert base != _synthetic_url("benzinga_6000stocks", "2020-01-01T00:00:00Z", "Headline A")
    assert base != _synthetic_url("fnspid_news", "2020-01-02T00:00:00Z", "Headline A")
    assert base != _synthetic_url("fnspid_news", "2020-01-01T00:00:00Z", "Headline B")


# ---------------------------------------------------------------------------
# HFCorpusClient._normalize
# ---------------------------------------------------------------------------


def test_normalize_splits_title_and_body_on_double_newline() -> None:
    raw = {
        "date": "2020-06-05T06:30:54Z",
        "text": "Stocks hit 52-week highs\n\nDetails follow in the next paragraph.",
        "extra_fields": '{"stocks":["A"],"url":"https://example.com/x","source":"Benzinga"}',
    }
    out = HFCorpusClient._normalize(raw, "fnspid_news")
    assert out is not None
    assert out["title"] == "Stocks hit 52-week highs"
    assert out["content"].startswith("Details follow")
    assert out["url"] == "https://example.com/x"
    assert out["source"] == "Benzinga"
    assert out["tickers"] == ["A"]
    assert out["publication_date"] == "2020-06-05T06:30:54Z"


def test_normalize_single_line_text_keeps_empty_content() -> None:
    raw = {
        "date": "2009-02-14T19:02:00Z",
        "text": "How Treasuries and ETFs Work",
        "extra_fields": '{"stocks":["NAV"]}',
    }
    out = HFCorpusClient._normalize(raw, "benzinga_6000stocks")
    assert out is not None
    assert out["title"] == "How Treasuries and ETFs Work"
    assert out["content"] == ""
    assert out["tickers"] == ["NAV"]


def test_normalize_uses_synthetic_url_when_missing() -> None:
    raw = {
        "date": "2000-01-01T00:00:00Z",
        "text": "Headline only — no URL",
        "extra_fields": '{"stocks":["AAPL"]}',
    }
    out = HFCorpusClient._normalize(raw, "sp500_daily_headlines")
    assert out is not None
    assert out["url"].startswith("hf://")


def test_normalize_skips_empty_text() -> None:
    assert HFCorpusClient._normalize({"text": "", "extra_fields": "{}"}, "x") is None
    assert HFCorpusClient._normalize({"text": None, "extra_fields": "{}"}, "x") is None


def test_normalize_tolerates_bad_extra_fields_json() -> None:
    # Malformed JSON should not crash — we just end up with no tickers/url.
    raw = {"date": "2020-01-01T00:00:00Z", "text": "Hello world", "extra_fields": "{not-json}"}
    out = HFCorpusClient._normalize(raw, "fnspid_news")
    assert out is not None
    assert out["tickers"] == []
    assert out["url"].startswith("hf://")


def test_normalize_prefers_trading_date_for_day_level_rows() -> None:
    raw = {
        "date": "2023-01-02T00:00:00Z",
        "text": "Headline",
        "extra_fields": (
            '{"stocks":["AAPL"],'
            '"date_trading":"2023-01-03T14:30:00Z",'
            '"time_precision":"day"}'
        ),
    }
    out = HFCorpusClient._normalize(raw, "sp500_daily_headlines")
    assert out is not None
    assert out["publication_date"] == "2023-01-03T14:30:00Z"


# ---------------------------------------------------------------------------
# date-range filter (used by the backfill orchestrator)
# ---------------------------------------------------------------------------


def test_date_in_range_no_bounds_accepts_everything() -> None:
    assert _date_in_range("2020-06-15T00:00:00Z", None, None) is True


def test_date_in_range_respects_bounds() -> None:
    start = datetime(2020, 1, 1)
    end = datetime(2020, 12, 31)
    assert _date_in_range("2020-06-15T00:00:00Z", start, end) is True
    assert _date_in_range("2019-12-31T23:59:59Z", start, end) is False
    assert _date_in_range("2021-01-01T00:00:01Z", start, end) is False


def test_date_in_range_unparseable_falls_through() -> None:
    # Deliberately lenient: we'd rather admit a weirdly-dated row
    # than silently drop it because of one malformed ISO string.
    assert _date_in_range("not-a-date", datetime(2020, 1, 1), None) is True
    assert _date_in_range(None, datetime(2020, 1, 1), None) is True


def test_date_in_range_half_open_bounds() -> None:
    # start-only / end-only bounds should work independently.
    assert _date_in_range(
        "2020-06-15T00:00:00Z", datetime(2020, 1, 1), None
    ) is True
    assert _date_in_range(
        "2019-06-15T00:00:00Z", datetime(2020, 1, 1), None
    ) is False
    assert _date_in_range(
        "2020-06-15T00:00:00Z", None, datetime(2020, 12, 31)
    ) is True
    assert _date_in_range(
        "2021-06-15T00:00:00Z", None, datetime(2020, 12, 31)
    ) is False
