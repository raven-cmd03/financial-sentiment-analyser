"""Top-level day-loop simulation engine.

``run_simulation(...)`` is the single entry point. It is intentionally
synchronous because it's invoked from (a) a Celery worker (sync context),
(b) a CLI script (trivial), and (c) tests (no event loop needed). The
LLM calls inside still block the loop but we rate-limit them so the
blocking is bounded and predictable.

Flow per run:
1. Load the run row, resolve the universe + date range.
2. Create 2N TraderAgent rows (treatment + control per declared profile).
3. Walk every trading day in order. On each day:
   - Build next-day's open-price map from market_data.
   - For each agent whose cadence fires today, build a variant briefing
     for ``D - 1`` and ask the LLM for orders; apply them against the
     portfolio at D's open; persist trades.
   - Persist a daily snapshot for every agent (fills are at the open so
     each agent's equity moves every day regardless of cadence).
4. At end of run, delegate to reporting to write artefacts + summary.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import date as date_cls, datetime, timezone
from decimal import Decimal
from typing import Callable, Iterable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SyncSessionLocal
from app.models import (
    AgentDailySnapshot,
    Company,
    MarketData,
    SentimentResult,
    SimulationRun,
    SimulationTrade,
    TraderAgent as TraderAgentRow,
)
from app.services.simulation.agent import TraderAgent
from app.services.simulation.briefing import build_briefing
from app.services.simulation.portfolio import Order, Portfolio, apply_orders
from app.services.simulation.profiles import (
    TRADER_PROFILES,
    VARIANTS,
    TraderProfile,
)

logger = logging.getLogger(__name__)

# ``AgentFactory`` is injected so tests can supply deterministic fakes
# without any Groq/network dependency. When left ``None`` the engine
# builds a real ``TraderAgent`` backed by ``langchain_groq.ChatGroq``.
AgentFactory = Callable[[TraderProfile, str], TraderAgent]


class RateLimiter:
    """Simple requests-per-minute limiter, thread-safe.

    We hold a sliding window of timestamps; when a new request would
    exceed ``rpm``, we sleep just long enough for the oldest call to
    fall outside the 60-second window.
    """

    def __init__(self, rpm: int):
        self._rpm = max(rpm, 1)
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self):
        while True:
            with self._lock:
                now = time.monotonic()
                self._timestamps = [t for t in self._timestamps if now - t < 60]
                if len(self._timestamps) < self._rpm:
                    self._timestamps.append(now)
                    return
                wait = 60 - (now - self._timestamps[0]) + 0.01
            if wait > 0:
                time.sleep(wait)


def _default_agent_factory(
    profile: TraderProfile, variant: str
) -> TraderAgent:
    """Production agent factory: wraps the configured provider LLM."""
    from app.services.simulation.llm_provider import (
        get_simulation_llm,
        get_structured_method,
    )

    llm = get_simulation_llm(temperature=0.2, streaming=False)
    return TraderAgent(
        profile=profile,
        variant=variant,
        llm=llm,
        structured_method=get_structured_method(),
    )


def _resolve_universe(
    session: Session, preferred: list[str] | None = None
) -> list[str]:
    """Return tickers that have both market data and at least some
    sentiment coverage, sorted for determinism.

    If ``preferred`` is given, it is intersected with the eligible set.
    """
    from sqlalchemy import func

    # Tickers with >= 30 days of prices.
    counts = (
        session.query(MarketData.ticker_symbol, func.count(MarketData.data_id))
        .group_by(MarketData.ticker_symbol)
        .all()
    )
    price_eligible = {t for t, c in counts if c >= 30}

    # Tickers that have at least one SentimentResult via article_companies.
    from app.models import ArticleCompany

    sent_rows = (
        session.query(Company.ticker_symbol)
        .join(ArticleCompany, ArticleCompany.company_id == Company.company_id)
        .join(
            SentimentResult,
            SentimentResult.article_id == ArticleCompany.article_id,
        )
        .group_by(Company.ticker_symbol)
        .all()
    )
    sent_eligible = {t for (t,) in sent_rows}

    universe = sorted(price_eligible & sent_eligible)
    if preferred:
        preferred_set = {t.upper() for t in preferred}
        universe = [t for t in universe if t in preferred_set]
    return universe


def _resolve_date_range(
    session: Session, universe: list[str], requested_start, requested_end
) -> tuple[date_cls | None, date_cls | None]:
    """Bound the simulation to dates where we have prices for at least
    one ticker in the universe and, for the start, at least one
    sentiment-scored news article exists at-or-before that date.

    IMPORTANT: the start bound uses ``news_articles.publication_date`` of
    articles that have a sentiment result — NOT
    ``sentiment_results.analyzed_date``, which is when FinBERT processed
    the article (often just "now" from a big batch job) and has nothing
    to do with the historical point-in-time availability of the signal.
    Using ``analyzed_date`` was a bug that compressed the window to just
    a few days.
    """
    if not universe:
        return None, None

    earliest_price = (
        session.query(MarketData.date)
        .filter(MarketData.ticker_symbol.in_(universe))
        .order_by(MarketData.date.asc())
        .first()
    )
    latest_price = (
        session.query(MarketData.date)
        .filter(MarketData.ticker_symbol.in_(universe))
        .order_by(MarketData.date.desc())
        .first()
    )
    if not earliest_price or not latest_price:
        return None, None

    from app.models import ArticleCompany, NewsArticle

    # Earliest sentiment-scored publication date for any ticker in the
    # universe. Joins ensure we only consider articles we actually
    # scored and that map to a company in the universe.
    earliest_sent_pub = (
        session.query(NewsArticle.publication_date)
        .join(ArticleCompany, ArticleCompany.article_id == NewsArticle.article_id)
        .join(Company, Company.company_id == ArticleCompany.company_id)
        .join(
            SentimentResult,
            SentimentResult.article_id == NewsArticle.article_id,
        )
        .filter(Company.ticker_symbol.in_(universe))
        .order_by(NewsArticle.publication_date.asc())
        .first()
    )

    start = earliest_price[0]
    if earliest_sent_pub and earliest_sent_pub[0]:
        sent_date = (
            earliest_sent_pub[0].date()
            if hasattr(earliest_sent_pub[0], "date")
            else earliest_sent_pub[0]
        )
        if sent_date > start:
            start = sent_date
    end = latest_price[0]

    if requested_start and requested_start > start:
        start = requested_start
    if requested_end and requested_end < end:
        end = requested_end

    if start > end:
        return None, None
    return start, end


def _load_price_matrix(
    session: Session, universe: list[str], start: date_cls, end: date_cls
) -> tuple[list[date_cls], dict[date_cls, dict[str, dict[str, float]]]]:
    """Load every relevant market_data row once.

    Returns:
        trading_days: sorted list of distinct dates with at least one row
            in range.
        by_day_ticker: nested mapping ``{date: {ticker: {"open": px, "close": px}}}``.
    """
    rows = (
        session.query(
            MarketData.date,
            MarketData.ticker_symbol,
            MarketData.open_price,
            MarketData.close_price,
        )
        .filter(MarketData.ticker_symbol.in_(universe))
        .filter(MarketData.date >= start)
        .filter(MarketData.date <= end)
        .order_by(MarketData.date.asc())
        .all()
    )
    by_day: dict[date_cls, dict[str, dict[str, float]]] = defaultdict(dict)
    for d, t, op, cp in rows:
        entry: dict[str, float] = {}
        if op is not None:
            entry["open"] = float(op)
        if cp is not None:
            entry["close"] = float(cp)
        by_day[d][t] = entry

    trading_days = sorted(by_day.keys())
    return trading_days, by_day


def _create_agent_rows(
    session: Session,
    run_id: int,
    starting_cash: float,
    profile_names: Iterable[str],
) -> dict[tuple[str, str], TraderAgentRow]:
    """Insert 2 rows per profile (treatment + control) and return them
    keyed by ``(profile_name, variant)``.
    """
    out: dict[tuple[str, str], TraderAgentRow] = {}
    for name in profile_names:
        profile = TRADER_PROFILES[name]
        for variant in VARIANTS:
            row = TraderAgentRow(
                run_id=run_id,
                profile_name=profile.name,
                variant=variant,
                starting_cash=Decimal(f"{starting_cash:.4f}"),
                final_cash=Decimal(f"{starting_cash:.4f}"),
                final_equity=Decimal(f"{starting_cash:.4f}"),
                final_return_pct=Decimal("0.0000"),
                trade_count=0,
                system_prompt=profile.system_prompt,
            )
            session.add(row)
            out[(profile.name, variant)] = row
    session.flush()  # populate agent_id
    return out


def run_simulation(
    run_id: int,
    profile_names: list[str] | None = None,
    universe_override: list[str] | None = None,
    start_date: date_cls | None = None,
    end_date: date_cls | None = None,
    agent_factory: AgentFactory | None = None,
    session: Session | None = None,
    report_writer: Callable[..., dict] | None = None,
) -> dict:
    """Execute the simulation identified by ``run_id``.

    All parameters beyond ``run_id`` are optional overrides; in
    production the CLI / Celery task pass only ``run_id`` and the engine
    reads configuration from the ``simulation_runs`` row itself.

    Returns a summary dict with ``{status, report_path, final_metrics}``.
    """
    settings = get_settings()
    owns_session = session is None
    if session is None:
        session = SyncSessionLocal()

    # Lazy import to keep engine importable without reporting's numpy/pandas
    # stack (unit tests don't need it).
    if report_writer is None:
        from app.services.simulation.reporting import write_run_reports

        report_writer = write_run_reports

    agent_factory = agent_factory or _default_agent_factory
    rate_limiter = RateLimiter(settings.SIMULATION_GROQ_RPM)

    starting_cash = float(settings.SIMULATION_STARTING_CASH)

    try:
        run: SimulationRun | None = session.get(SimulationRun, run_id)
        if run is None:
            raise ValueError(f"SimulationRun {run_id} not found")

        run.status = "running"
        session.flush()

        profiles = profile_names or list(TRADER_PROFILES.keys())
        unknown = [p for p in profiles if p not in TRADER_PROFILES]
        if unknown:
            raise ValueError(f"Unknown profile(s): {unknown}")

        universe = _resolve_universe(session, universe_override)
        if not universe:
            raise RuntimeError(
                "Simulation universe is empty — no tickers have both "
                "market_data and sentiment_results."
            )

        start, end = _resolve_date_range(session, universe, start_date, end_date)
        if not start or not end:
            raise RuntimeError("No overlapping date range with data for the universe")

        trading_days, by_day = _load_price_matrix(session, universe, start, end)
        if len(trading_days) < 2:
            raise RuntimeError("Need at least 2 trading days in range")

        run.universe = universe
        run.start_date = trading_days[0]
        run.end_date = trading_days[-1]
        run.config = {
            **(run.config or {}),
            "profiles": profiles,
            "starting_cash": starting_cash,
            "groq_model": settings.GROQ_MODEL,
            "rpm": settings.SIMULATION_GROQ_RPM,
            "llm_provider": settings.SIMULATION_LLM_PROVIDER,
            "fireworks_model": settings.FIREWORKS_MODEL,
            "progress_interval_sec": settings.SIMULATION_PROGRESS_INTERVAL_SEC,
            "llm_timeout_sec": settings.SIMULATION_LLM_TIMEOUT_SEC,
            "llm_max_retries": settings.SIMULATION_LLM_MAX_RETRIES,
        }
        session.flush()

        agent_rows = _create_agent_rows(session, run_id, starting_cash, profiles)

        # Build in-memory agent state: the row's agent_id + a fresh Portfolio.
        # Keyed by (profile, variant) so cadence lookups are cheap.
        agent_portfolios: dict[tuple[str, str], Portfolio] = {
            key: Portfolio(cash=starting_cash, holdings={})
            for key in agent_rows
        }
        agent_llms: dict[tuple[str, str], TraderAgent] = {}
        for (prof_name, variant) in agent_rows:
            profile = TRADER_PROFILES[prof_name]
            try:
                agent_llms[(prof_name, variant)] = agent_factory(profile, variant)
            except Exception as exc:
                logger.exception(
                    "Failed to build agent for %s/%s — disabling", prof_name, variant
                )
                agent_llms[(prof_name, variant)] = None  # type: ignore[assignment]

        trade_counts: dict[tuple[str, str], int] = defaultdict(int)
        equity_curves: dict[tuple[str, str], list[float]] = {
            key: [] for key in agent_rows
        }

        universe_set = set(universe)

        # Progress snapshots: tick every SIMULATION_PROGRESS_INTERVAL_SEC
        # wall-clock seconds so operators can watch a long run without
        # tailing the celery log. Disabled if the interval is <= 0.
        progress_interval = max(0.0, float(settings.SIMULATION_PROGRESS_INTERVAL_SEC))
        run_started_at = time.monotonic()
        next_progress_at = (
            run_started_at + progress_interval if progress_interval > 0 else None
        )
        progress_counter = 0

        # ``i`` indexes ``trading_days``. The briefing uses data <= D-1 and
        # orders fill on D's open. So we start from i = 1, and each agent's
        # cadence is measured against how many decision days have elapsed.
        decision_counters: dict[tuple[str, str], int] = defaultdict(int)

        for i in range(len(trading_days)):
            today = trading_days[i]
            # Build the prices map for *today's* open (used for fills) and
            # today's close (used for end-of-day equity valuation).
            open_prices = {
                t: by_day[today].get(t, {}).get("open")
                for t in universe
                if by_day[today].get(t, {}).get("open") is not None
            }
            close_prices = {
                t: by_day[today].get(t, {}).get("close")
                for t in universe
                if by_day[today].get(t, {}).get("close") is not None
            }
            # Fallback: use open as close if we only have one side.
            eod_prices = {**open_prices, **close_prices}

            # ------------- agent decisions for day ``today`` -------------
            if i > 0:
                briefing_cutoff = trading_days[i - 1]
                # Build both briefings once per day (shared across profiles
                # within a variant) — saves a lot of DB work.
                briefings: dict[str, dict] = {}
                for (prof_name, variant), agent in agent_llms.items():
                    if agent is None:
                        continue
                    profile = TRADER_PROFILES[prof_name]
                    decision_counters[(prof_name, variant)] += 1
                    # Cadence: fire on decision days 1, 1+N, 1+2N, ... where
                    # N is profile.cadence_days. cadence_days == 1 fires
                    # every day; cadence_days == 7 fires weekly; etc.
                    counter = decision_counters[(prof_name, variant)]
                    if (counter - 1) % profile.cadence_days != 0:
                        continue

                    key_var = variant
                    if key_var not in briefings:
                        briefings[key_var] = build_briefing(
                            briefing_cutoff, universe, session, key_var
                        )
                    briefing = briefings[key_var]

                    portfolio = agent_portfolios[(prof_name, variant)]
                    rate_limiter.acquire()
                    try:
                        orders: list[Order] = agent.decide(
                            briefing, portfolio, today.isoformat()
                        )
                    except Exception:
                        logger.exception(
                            "Agent %s/%s decide() crashed on %s — skipping day",
                            prof_name,
                            variant,
                            today,
                        )
                        orders = []

                    new_portfolio, executed, rejections = apply_orders(
                        portfolio, orders, open_prices, universe_set
                    )
                    if rejections:
                        logger.debug(
                            "Agent %s/%s rejections on %s: %s",
                            prof_name,
                            variant,
                            today,
                            rejections,
                        )
                    agent_portfolios[(prof_name, variant)] = new_portfolio

                    agent_row = agent_rows[(prof_name, variant)]
                    for ex in executed:
                        trade = SimulationTrade(
                            agent_id=agent_row.agent_id,
                            date=today,
                            ticker=ex.ticker,
                            side=ex.side,
                            shares=Decimal(f"{ex.shares:.6f}"),
                            price=Decimal(f"{ex.price:.4f}"),
                            cash_after=Decimal(f"{ex.cash_after:.4f}"),
                            equity_after=Decimal(f"{ex.equity_after:.4f}"),
                            reasoning=ex.reasoning or "",
                        )
                        session.add(trade)
                        trade_counts[(prof_name, variant)] += 1

            # ------------- end-of-day snapshot for every agent -------------
            eod_equity_by_key: dict[tuple[str, str], float] = {}
            for key, portfolio in agent_portfolios.items():
                equity = portfolio.equity(eod_prices)
                eod_equity_by_key[key] = equity
                equity_curves[key].append(equity)
                agent_row = agent_rows[key]
                snap = AgentDailySnapshot(
                    agent_id=agent_row.agent_id,
                    date=today,
                    cash=Decimal(f"{portfolio.cash:.4f}"),
                    holdings={t: float(s) for t, s in portfolio.holdings.items()},
                    total_equity=Decimal(f"{equity:.4f}"),
                )
                session.merge(snap)

            session.flush()

            # ------------- periodic progress snapshot -------------
            if next_progress_at is not None:
                now_mono = time.monotonic()
                if now_mono >= next_progress_at:
                    progress_counter += 1
                    try:
                        from app.services.simulation.reporting import (
                            write_progress_snapshot,
                        )

                        agent_state = []
                        for key, portfolio in agent_portfolios.items():
                            agent_state.append(
                                {
                                    "profile": key[0],
                                    "variant": key[1],
                                    "cash": float(portfolio.cash),
                                    "equity": float(eod_equity_by_key[key]),
                                    "trade_count": trade_counts[key],
                                    "starting_cash": starting_cash,
                                }
                            )
                        write_progress_snapshot(
                            run_id=run_id,
                            snapshot_number=progress_counter,
                            elapsed_seconds=now_mono - run_started_at,
                            day_index=i,
                            total_days=len(trading_days),
                            current_day=today,
                            agent_state=agent_state,
                            output_base=settings.SIMULATION_OUTPUT_DIR,
                        )
                    except Exception:  # pylint: disable=broad-except
                        # Must never kill the run; write_progress_snapshot
                        # already logs its own internal exception, but we
                        # also guard the import + call site.
                        logger.exception(
                            "Progress snapshot #%d failed", progress_counter
                        )
                    next_progress_at = now_mono + progress_interval

        # --------------- finalise agent rows + write reports ---------------
        from app.services.simulation.metrics import compute_agent_metrics

        final_payload_for_agents: list[dict] = []
        for key, portfolio in agent_portfolios.items():
            curve = equity_curves[key]
            metrics = compute_agent_metrics(
                curve, trade_count=trade_counts[key]
            )
            final_equity = curve[-1] if curve else starting_cash
            final_return = (final_equity - starting_cash) / starting_cash if starting_cash else 0.0
            agent_row = agent_rows[key]
            agent_row.final_cash = Decimal(f"{portfolio.cash:.4f}")
            agent_row.final_equity = Decimal(f"{final_equity:.4f}")
            agent_row.final_return_pct = Decimal(f"{final_return * 100:.4f}")
            agent_row.sharpe = (
                Decimal(f"{metrics.sharpe:.4f}") if metrics.sharpe is not None else None
            )
            agent_row.max_drawdown = Decimal(f"{metrics.max_drawdown_pct:.4f}")
            agent_row.trade_count = trade_counts[key]

            final_payload_for_agents.append(
                {
                    "agent_id": agent_row.agent_id,
                    "profile": key[0],
                    "variant": key[1],
                    "metrics": metrics,
                    "equity_curve": curve,
                    "final_cash": portfolio.cash,
                    "final_equity": final_equity,
                    "holdings": dict(portfolio.holdings),
                }
            )
        session.flush()

        # Persist completed status *before* reporting so an LLM narrative
        # hiccup can't revert the run to "running".
        run.status = "completed"
        session.commit()

        report_summary = report_writer(
            run_id=run_id,
            run=run,
            agents=final_payload_for_agents,
            trading_days=trading_days,
            session=session,
            settings=settings,
        )

        # Refresh run with report path + rollup metrics produced by reporting.
        run = session.get(SimulationRun, run_id)
        run.report_path = report_summary.get("report_path")
        run.final_metrics = report_summary.get("final_metrics", {})
        session.commit()

        return {
            "run_id": run_id,
            "status": "completed",
            "report_path": run.report_path,
            "final_metrics": run.final_metrics,
        }

    except Exception as exc:
        logger.exception("Simulation run %s failed", run_id)
        session.rollback()
        try:
            run = session.get(SimulationRun, run_id)
            if run is not None:
                run.status = "failed"
                run.error = str(exc)[:4000]
                session.commit()
        except Exception:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()
