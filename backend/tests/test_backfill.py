"""Unit tests for the historical backfill plumbing.

Covers the pieces that don't need a live DB / worker:
- Alpha Vantage time-window formatting & param wiring
- Rate-limit signalling (raise_on_rate_limit)
- Time-window generator (monotonic, bounded, backwards-walking)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.clients.alpha_vantage import (
    AlphaVantageClient,
    AlphaVantageError,
    _format_av_window,
)
from app.services.backfill import iter_time_windows


# ---------------------------------------------------------------------------
# _format_av_window
# ---------------------------------------------------------------------------


def test_format_av_window_naive_treated_as_utc() -> None:
    assert _format_av_window(datetime(2024, 6, 15, 13, 45)) == "20240615T1345"


def test_format_av_window_aware_converted_to_utc() -> None:
    # 13:45 in UTC+2 == 11:45 UTC
    tz = timezone(timedelta(hours=2))
    dt = datetime(2024, 6, 15, 13, 45, tzinfo=tz)
    assert _format_av_window(dt) == "20240615T1145"


# ---------------------------------------------------------------------------
# fetch_news time-window / rate-limit behaviour
# ---------------------------------------------------------------------------


class _StubResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


async def test_fetch_news_forwards_time_window_params() -> None:
    async with AlphaVantageClient(api_key="test") as client:
        captured: dict = {}

        async def fake_request(method, url, *, params=None, **_kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["params"] = params
            return _StubResponse({"feed": []})

        client._request = fake_request  # type: ignore[assignment]

        await client.fetch_news(
            "AAPL",
            max_results=500,
            time_from=datetime(2023, 1, 1),
            time_to=datetime(2023, 2, 1),
            sort="EARLIEST",
        )

    assert captured["params"]["time_from"] == "20230101T0000"
    assert captured["params"]["time_to"] == "20230201T0000"
    assert captured["params"]["sort"] == "EARLIEST"
    # limit gets clamped to 1000 (AV's hard cap) but passes 500 through.
    assert captured["params"]["limit"] == 500
    assert captured["params"]["tickers"] == "AAPL"


async def test_fetch_news_raises_on_rate_limit_when_asked() -> None:
    async with AlphaVantageClient(api_key="test") as client:
        async def fake_request(method, url, *, params=None, **_kwargs):
            return _StubResponse(
                {"Note": "Thank you for using Alpha Vantage! Our standard API..."}
            )

        client._request = fake_request  # type: ignore[assignment]

        # Default behaviour: returns empty list (preserves backward compat).
        articles = await client.fetch_news("AAPL")
        assert articles == []

        # Opt-in: raises so the backfill can stop cleanly.
        with pytest.raises(AlphaVantageError):
            await client.fetch_news("AAPL", raise_on_rate_limit=True)


async def test_fetch_news_clamps_limit_to_av_ceiling() -> None:
    async with AlphaVantageClient(api_key="test") as client:
        captured: dict = {}

        async def fake_request(method, url, *, params=None, **_kwargs):
            captured["params"] = params
            return _StubResponse({"feed": []})

        client._request = fake_request  # type: ignore[assignment]
        await client.fetch_news("AAPL", max_results=5_000)
    # AV's hard cap is 1000.
    assert captured["params"]["limit"] == 1000


# ---------------------------------------------------------------------------
# iter_time_windows
# ---------------------------------------------------------------------------


def test_iter_time_windows_walks_backwards_and_is_inclusive() -> None:
    end = datetime(2024, 1, 1)
    start = datetime(2023, 10, 1)

    windows = list(iter_time_windows(start=start, end=end, window_days=30))

    # Walking backwards: each window's end should equal the previous
    # window's start (no gaps, no overlap).
    assert windows[0][1] == end
    for (a_start, _a_end), (_b_start, b_end) in zip(windows, windows[1:]):
        assert a_start == b_end

    # Earliest window's start must be clamped to ``start``.
    assert windows[-1][0] == start

    # Each window is at most ``window_days`` long.
    for a_start, a_end in windows:
        assert (a_end - a_start).days <= 30


def test_iter_time_windows_empty_when_end_leq_start() -> None:
    t = datetime(2024, 1, 1)
    assert list(iter_time_windows(start=t, end=t, window_days=30)) == []
    assert list(
        iter_time_windows(start=t, end=t - timedelta(days=1), window_days=30)
    ) == []


def test_iter_time_windows_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError):
        list(
            iter_time_windows(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 2, 1),
                window_days=0,
            )
        )
