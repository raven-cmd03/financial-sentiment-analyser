"""End-to-end test for the backtest trader-agent simulation engine.

Uses fake agent doubles so the test is deterministic, needs no Groq
key, and runs in <1s. Boots a SQLite in-memory DB with the full schema,
seeds 2 tickers + 10 days of prices + a splash of sentiment, then runs
the engine end-to-end with a single profile in both variants.
"""

from __future__ import annotations

from datetime import datetime, timedelta, date as date_cls
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
# Importing every model registers the tables on Base.metadata. If you
# drop an import here, ``create_all`` silently omits that table.
from app.models import (  # noqa: F401
    Company,
    NewsArticle,
    ArticleCompany,
    SentimentResult,
    MarketData,
    SimulationRun,
    TraderAgent,
    SimulationTrade,
    AgentDailySnapshot,
)
from app.services.simulation.agent import TraderAgent as TraderAgentRunner
from app.services.simulation.portfolio import Order
from app.services.simulation.profiles import TRADER_PROFILES, TraderProfile


# ---------------------------------------------------------------------------
# Fake agent doubles. Each records the briefing it saw so we can inspect
# what variant-specific content actually reached the LLM layer.
# ---------------------------------------------------------------------------


class _RecordingAgent(TraderAgentRunner):
    def __init__(self, profile: TraderProfile, variant: str, strategy):
        super().__init__(profile=profile, variant=variant, llm=None)
        self._strategy = strategy
        self.briefings_seen: list[dict] = []

    def decide(self, briefing, portfolio, day):
        self.briefings_seen.append(briefing)
        return self._strategy(briefing, portfolio, day)


def _treatment_strategy(briefing, portfolio, day):
    """Treatment fake: buy the ticker with the most positive sentiment,
    if one exists and we hold cash. Otherwise hold.
    """
    if portfolio.cash <= 0:
        return []
    best_ticker = None
    best_score = 0.0
    for ticker, info in briefing["tickers"].items():
        s = (info.get("sentiment") or {}).get("mean_score", 0.0) or 0.0
        if s > best_score:
            best_score = s
            best_ticker = ticker
    if not best_ticker:
        return []
    return [
        Order(
            ticker=best_ticker,
            side="buy",
            size_pct=0.5,
            reasoning="fake treatment: best sentiment",
        )
    ]


def _control_strategy(briefing, portfolio, day):
    """Control fake: buy the ticker with the largest 1-day price jump."""
    if portfolio.cash <= 0:
        return []
    best_ticker = None
    best_ret = 0.0
    for ticker, info in briefing["tickers"].items():
        r = info.get("ret_1d") or 0.0
        if r > best_ret:
            best_ret = r
            best_ticker = ticker
    if not best_ticker:
        return []
    return [
        Order(
            ticker=best_ticker,
            side="buy",
            size_pct=0.5,
            reasoning="fake control: biggest 1d price move",
        )
    ]


# ---------------------------------------------------------------------------
# Fixture: seeded sqlite session
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    aapl = Company(company_name="Apple", ticker_symbol="AAPL", sector="Tech")
    msft = Company(company_name="Microsoft", ticker_symbol="MSFT", sector="Tech")
    session.add_all([aapl, msft])
    session.flush()

    base_date = date_cls(2025, 1, 6)  # a Monday
    # Need >=30 trading days for _resolve_universe to accept the ticker.
    days = []
    d = base_date
    while len(days) < 35:
        if d.weekday() < 5:
            days.append(d)
        d = d + timedelta(days=1)

    # Prices: AAPL steadily climbs, MSFT oscillates slightly.
    for i, day in enumerate(days):
        aapl_open = 100 + i
        aapl_close = aapl_open + 0.5
        msft_open = 200 + (i % 3)
        msft_close = msft_open + 0.3
        session.add(
            MarketData(
                ticker_symbol="AAPL",
                date=day,
                open_price=aapl_open,
                close_price=aapl_close,
                high_price=aapl_close + 1,
                low_price=aapl_open - 1,
                volume=1000,
            )
        )
        session.add(
            MarketData(
                ticker_symbol="MSFT",
                date=day,
                open_price=msft_open,
                close_price=msft_close,
                high_price=msft_close + 1,
                low_price=msft_open - 1,
                volume=1000,
            )
        )

    # Sentiment: AAPL very positive, MSFT mildly negative, across the window.
    for i, day in enumerate(days):
        pub = datetime.combine(day, datetime.min.time())
        for company, pos, neg, lbl in (
            (aapl, 0.9, 0.05, "positive"),
            (msft, 0.1, 0.7, "negative"),
        ):
            article_id = f"{company.ticker_symbol}-{i}"
            session.add(
                NewsArticle(
                    article_id=article_id,
                    title=f"{company.ticker_symbol} update {i}",
                    content="body",
                    source="test",
                    publication_date=pub,
                    collected_date=pub,
                )
            )
            session.flush()
            session.add(
                ArticleCompany(
                    article_id=article_id, company_id=company.company_id
                )
            )
            session.add(
                SentimentResult(
                    article_id=article_id,
                    sentiment_label=lbl,
                    positive_score=pos,
                    negative_score=neg,
                    neutral_score=max(0.0, 1 - pos - neg),
                    confidence=max(pos, neg),
                    analyzed_date=pub,
                )
            )
    session.commit()

    run = SimulationRun(status="pending", universe=[], config={})
    session.add(run)
    session.commit()
    session.refresh(run)

    yield session, run.run_id, days
    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# The actual test
# ---------------------------------------------------------------------------


def test_end_to_end_simulation(tmp_path, seeded_session, monkeypatch):
    session, run_id, trading_days = seeded_session

    # Keep all report artefacts inside pytest's tmp dir and lift the RPM
    # limit so the rate limiter doesn't sleep 60s mid-test.
    monkeypatch.setenv("SIMULATION_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SIMULATION_GROQ_RPM", "100000")
    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = get_settings()
    assert settings.SIMULATION_OUTPUT_DIR == str(tmp_path)

    from app.services.simulation.engine import run_simulation

    assert "day_trader" in TRADER_PROFILES
    # Capture per-variant recording agents so we can inspect briefings later.
    captured: dict[str, _RecordingAgent] = {}

    def factory(prof: TraderProfile, variant: str) -> _RecordingAgent:
        strategy = _treatment_strategy if variant == "treatment" else _control_strategy
        agent = _RecordingAgent(prof, variant, strategy)
        captured[variant] = agent
        return agent

    result = run_simulation(
        run_id=run_id,
        profile_names=["day_trader"],
        universe_override=["AAPL", "MSFT"],
        agent_factory=factory,
        session=session,
        # Skip the Groq narrative path entirely; still writes markdown.
        report_writer=None,
    )

    assert result["status"] == "completed"
    assert result["report_path"]
    report_dir = Path(result["report_path"])
    assert report_dir.exists()
    assert (report_dir / "run_summary.md").exists()
    assert (report_dir / "run_summary.json").exists()
    assert (report_dir / "per_profile" / "day_trader.md").exists()
    assert (report_dir / "per_trader" / "day_trader_treatment.md").exists()
    assert (report_dir / "per_trader" / "day_trader_control.md").exists()

    # ---- Agent row assertions ----
    agent_rows = (
        session.query(TraderAgent).filter(TraderAgent.run_id == run_id).all()
    )
    assert len(agent_rows) == 2
    variants = {a.variant for a in agent_rows}
    assert variants == {"treatment", "control"}
    for a in agent_rows:
        assert a.profile_name == "day_trader"
        assert float(a.starting_cash) == pytest.approx(
            float(settings.SIMULATION_STARTING_CASH)
        )
        assert float(a.final_equity) > 0

    # ---- Briefing arm separation ----
    # Treatment saw sentiment keys; control did NOT.
    t_briefs = captured["treatment"].briefings_seen
    c_briefs = captured["control"].briefings_seen
    assert t_briefs, "treatment agent should have been asked at least once"
    assert c_briefs, "control agent should have been asked at least once"
    for b in t_briefs:
        for ticker, info in b["tickers"].items():
            assert "sentiment" in info, f"treatment briefing missing sentiment for {ticker}"
            assert "vol_20d" not in info
    for b in c_briefs:
        for ticker, info in b["tickers"].items():
            assert "sentiment" not in info, (
                f"control briefing leaked sentiment data for {ticker}"
            )
            assert "vol_20d" in info

    # ---- Trades + accounting ----
    trades = (
        session.query(SimulationTrade)
        .join(TraderAgent, TraderAgent.agent_id == SimulationTrade.agent_id)
        .filter(TraderAgent.run_id == run_id)
        .all()
    )
    assert trades, "engine recorded zero trades despite fakes buying every cadence"
    # Treatment fake always picks AAPL (positive sentiment); control fake
    # picks by largest 1d return (AAPL, which ticks up monotonically).
    treatment_id = next(a.agent_id for a in agent_rows if a.variant == "treatment")
    treatment_trades = [t for t in trades if t.agent_id == treatment_id]
    assert all(t.ticker == "AAPL" for t in treatment_trades)

    # ---- Snapshots ----
    snapshots = (
        session.query(AgentDailySnapshot)
        .join(TraderAgent, TraderAgent.agent_id == AgentDailySnapshot.agent_id)
        .filter(TraderAgent.run_id == run_id)
        .all()
    )
    # Every agent should have one snapshot per trading day.
    assert len(snapshots) == len(trading_days) * len(agent_rows)
    for s in snapshots:
        assert float(s.total_equity) > 0
        assert float(s.cash) >= 0


def test_progress_snapshots_are_written(tmp_path, seeded_session, monkeypatch):
    """With a tiny progress interval, each day's loop iteration should
    fire a progress snapshot — we should end with >=1 snapshot file
    on disk and the latest.md/latest.json convenience copies."""
    session, run_id, trading_days = seeded_session

    monkeypatch.setenv("SIMULATION_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SIMULATION_GROQ_RPM", "100000")
    monkeypatch.setenv("SIMULATION_PROGRESS_INTERVAL_SEC", "0.0001")
    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = get_settings()
    assert settings.SIMULATION_PROGRESS_INTERVAL_SEC <= 0.001

    from app.services.simulation.engine import run_simulation

    def factory(prof: TraderProfile, variant: str) -> _RecordingAgent:
        strategy = _treatment_strategy if variant == "treatment" else _control_strategy
        return _RecordingAgent(prof, variant, strategy)

    result = run_simulation(
        run_id=run_id,
        profile_names=["day_trader"],
        universe_override=["AAPL", "MSFT"],
        agent_factory=factory,
        session=session,
        report_writer=None,
    )

    assert result["status"] == "completed"
    progress_dir = tmp_path / str(run_id) / "progress"
    assert progress_dir.exists(), "progress directory was not created"

    snap_md = sorted(progress_dir.glob("snapshot_*.md"))
    snap_json = sorted(progress_dir.glob("snapshot_*.json"))
    assert snap_md, "no progress snapshot markdown written"
    assert len(snap_md) == len(snap_json)

    assert (progress_dir / "latest.md").exists()
    assert (progress_dir / "latest.json").exists()

    import json as _json

    payload = _json.loads((progress_dir / "latest.json").read_text())
    assert payload["run_id"] == run_id
    assert payload["total_days"] == len(trading_days)
    assert 0.0 <= payload["progress_pct"] <= 100.0
    assert payload["leaderboard"], "leaderboard should have at least one row"
    for row in payload["leaderboard"]:
        assert {"profile", "variant", "equity", "return_pct", "trade_count"} <= row.keys()


def test_apply_orders_basic_accounting():
    from app.services.simulation.portfolio import Portfolio, apply_orders

    p = Portfolio(cash=1000.0, holdings={})
    orders = [Order(ticker="AAPL", side="buy", size_pct=0.5, reasoning="r")]
    prices = {"AAPL": 100.0}

    new_p, executed, rejections = apply_orders(p, orders, prices, universe={"AAPL"})

    assert rejections == []
    assert len(executed) == 1
    assert executed[0].shares == pytest.approx(5.0)
    assert new_p.cash == pytest.approx(500.0)
    assert new_p.holdings["AAPL"] == pytest.approx(5.0)

    # Sell half of what we own.
    sell = [Order(ticker="AAPL", side="sell", size_pct=0.5, reasoning="r2")]
    p2, exec2, _ = apply_orders(new_p, sell, prices, universe={"AAPL"})
    assert p2.holdings["AAPL"] == pytest.approx(2.5)
    assert p2.cash == pytest.approx(750.0)
    assert exec2[0].shares == pytest.approx(2.5)


def test_apply_orders_rejects_unknown_ticker_and_clamps_oversize():
    from app.services.simulation.portfolio import Portfolio, apply_orders

    p = Portfolio(cash=500.0, holdings={})
    orders = [
        Order(ticker="NOPE", side="buy", size_pct=0.5, reasoning=""),
        Order(ticker="AAPL", side="buy", size_pct=5.0, reasoning=""),  # over-1.0, clamped
    ]
    new_p, executed, rejections = apply_orders(
        p, orders, {"AAPL": 50.0}, universe={"AAPL"}
    )
    # NOPE rejected; AAPL buy clamped to 100% of cash.
    assert len(executed) == 1
    assert executed[0].ticker == "AAPL"
    assert executed[0].shares == pytest.approx(10.0)
    assert new_p.cash == pytest.approx(0.0)
    assert any("NOPE" in r for r in rejections)


def test_apply_orders_rejects_sell_without_holdings():
    from app.services.simulation.portfolio import Portfolio, apply_orders

    p = Portfolio(cash=500.0, holdings={})
    orders = [Order(ticker="AAPL", side="sell", size_pct=1.0, reasoning="")]
    new_p, executed, rejections = apply_orders(
        p, orders, {"AAPL": 50.0}, universe={"AAPL"}
    )
    assert executed == []
    assert new_p.cash == pytest.approx(500.0)
    assert any("sell rejected" in r for r in rejections)
