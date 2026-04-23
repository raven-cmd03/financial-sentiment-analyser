"""Simulation reporting: per-trader, per-profile head-to-head, aggregate.

All artefacts are written to ``SIMULATION_OUTPUT_DIR/<run_id>/``:

- ``run_summary.md``             — top-level leaderboard + lift table + LLM narrative
- ``run_summary.json``           — same data, machine-readable
- ``per_profile/<profile>.md``   — head-to-head report per profile
- ``per_trader/<profile>_<variant>.md`` + .json — full trader log
- ``briefing_samples.md``        — paired treatment/control briefings for audit
"""

from __future__ import annotations

import json
import logging
from datetime import date as date_cls
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import SimulationRun, SimulationTrade, TraderAgent as TraderAgentRow
from app.services.simulation.briefing import build_briefing
from app.services.simulation.metrics import AgentMetrics, PairMetrics, pair_metrics
from app.services.simulation.profiles import TRADER_PROFILES

logger = logging.getLogger(__name__)


def _sparkline(values: Iterable[float]) -> str:
    """Render a monospace sparkline using box-drawing blocks."""
    vs = [v for v in values if v is not None]
    if not vs:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    lo, hi = min(vs), max(vs)
    if hi == lo:
        return chars[0] * len(vs)
    out = []
    span = hi - lo
    for v in vs:
        idx = int(((v - lo) / span) * (len(chars) - 1))
        out.append(chars[idx])
    return "".join(out)


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:+.2f}%"


def _fmt_num(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def _money(x: float | None) -> str:
    if x is None:
        return "—"
    return f"${x:,.2f}"


def _run_dir(run_id: int, base: str) -> Path:
    path = Path(base) / str(run_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "per_profile").mkdir(exist_ok=True)
    (path / "per_trader").mkdir(exist_ok=True)
    return path


def _write_per_trader(
    run_dir: Path,
    agent: dict,
    trades: list[SimulationTrade],
    trading_days: list[date_cls],
) -> None:
    metrics: AgentMetrics = agent["metrics"]
    name = f"{agent['profile']}_{agent['variant']}"
    md_path = run_dir / "per_trader" / f"{name}.md"
    json_path = run_dir / "per_trader" / f"{name}.json"

    spark = _sparkline(agent["equity_curve"])
    lines = [
        f"# {agent['profile']} ({agent['variant']})",
        "",
        f"- Starting equity: {_money(metrics.starting_equity)}",
        f"- Final equity: {_money(metrics.final_equity)}",
        f"- Total return: {_fmt_pct(metrics.total_return_pct)}",
        f"- Annualised return: {_fmt_pct(metrics.annualised_return_pct)}",
        f"- Sharpe (ann.): {_fmt_num(metrics.sharpe, 3)}",
        f"- Max drawdown: {_fmt_pct(metrics.max_drawdown_pct)}",
        f"- Trade count: {metrics.trade_count}",
        "",
        f"Equity curve: `{spark}`",
        "",
        "## Trade log",
        "",
        "| Date | Ticker | Side | Shares | Price | Cash After | Equity After | Reasoning |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for t in trades:
        reason = (t.reasoning or "").replace("\n", " ").replace("|", "\\|")
        if len(reason) > 180:
            reason = reason[:177] + "…"
        lines.append(
            "| {d} | {tk} | {s} | {sh} | {p} | {c} | {e} | {r} |".format(
                d=t.date.isoformat() if t.date else "—",
                tk=t.ticker,
                s=t.side,
                sh=f"{float(t.shares):.4f}",
                p=f"${float(t.price):.2f}",
                c=f"${float(t.cash_after):.2f}",
                e=f"${float(t.equity_after):.2f}",
                r=reason,
            )
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    json_path.write_text(
        json.dumps(
            {
                "profile": agent["profile"],
                "variant": agent["variant"],
                "metrics": {
                    "total_return_pct": metrics.total_return_pct,
                    "annualised_return_pct": metrics.annualised_return_pct,
                    "sharpe": metrics.sharpe,
                    "max_drawdown_pct": metrics.max_drawdown_pct,
                    "trade_count": metrics.trade_count,
                    "final_equity": metrics.final_equity,
                    "starting_equity": metrics.starting_equity,
                },
                "equity_curve": [
                    {"date": d.isoformat(), "equity": v}
                    for d, v in zip(trading_days, agent["equity_curve"])
                ],
                "trades": [
                    {
                        "date": t.date.isoformat() if t.date else None,
                        "ticker": t.ticker,
                        "side": t.side,
                        "shares": float(t.shares),
                        "price": float(t.price),
                        "cash_after": float(t.cash_after),
                        "equity_after": float(t.equity_after),
                        "reasoning": t.reasoning or "",
                    }
                    for t in trades
                ],
                "final_holdings": agent["holdings"],
            },
            default=str,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_per_profile(
    run_dir: Path,
    profile_name: str,
    treatment: dict,
    control: dict,
    trades_by_agent: dict[int, list[SimulationTrade]],
    pair: PairMetrics,
) -> None:
    profile = TRADER_PROFILES.get(profile_name)
    title = profile.display_name if profile else profile_name

    tm: AgentMetrics = treatment["metrics"]
    cm: AgentMetrics = control["metrics"]

    lines = [
        f"# {title} — treatment vs control",
        "",
        f"_{profile.description if profile else ''}_",
        "",
        "| Metric | Treatment (with sentiment tool) | Control (price-only) | Δ (treatment − control) |",
        "| --- | --- | --- | --- |",
        f"| Total return | {_fmt_pct(tm.total_return_pct)} | {_fmt_pct(cm.total_return_pct)} | "
        f"{_fmt_pct(pair.return_lift_pct)} |",
        f"| Sharpe (ann.) | {_fmt_num(tm.sharpe, 3)} | {_fmt_num(cm.sharpe, 3)} | "
        f"{_fmt_num(pair.sharpe_lift, 3)} |",
        f"| Max drawdown | {_fmt_pct(tm.max_drawdown_pct)} | {_fmt_pct(cm.max_drawdown_pct)} | "
        f"{_fmt_pct(pair.max_dd_delta)} |",
        f"| Trade count | {tm.trade_count} | {cm.trade_count} | "
        f"{tm.trade_count - cm.trade_count:+d} |",
        f"| Final equity | {_money(tm.final_equity)} | {_money(cm.final_equity)} | "
        f"{_money(tm.final_equity - cm.final_equity)} |",
        f"| Equity-curve correlation | — | — | "
        f"{_fmt_num(pair.equity_correlation, 3)} |",
        "",
        f"Treatment equity curve: `{_sparkline(treatment['equity_curve'])}`  ",
        f"Control   equity curve: `{_sparkline(control['equity_curve'])}`",
        "",
    ]

    # Divergent trades: dates where one arm traded a ticker and the other did not.
    t_trades = trades_by_agent.get(treatment["agent_id"], [])
    c_trades = trades_by_agent.get(control["agent_id"], [])
    t_keys = {(t.date, t.ticker) for t in t_trades}
    c_keys = {(t.date, t.ticker) for t in c_trades}
    only_t = [t for t in t_trades if (t.date, t.ticker) not in c_keys][:10]
    only_c = [t for t in c_trades if (t.date, t.ticker) not in t_keys][:10]

    if only_t:
        lines.append("## Trades only treatment took (up to 10)")
        lines.append("")
        lines.append("| Date | Ticker | Side | Reasoning |")
        lines.append("| --- | --- | --- | --- |")
        for t in only_t:
            reason = (t.reasoning or "").replace("\n", " ").replace("|", "\\|")[:160]
            lines.append(f"| {t.date} | {t.ticker} | {t.side} | {reason} |")
        lines.append("")

    if only_c:
        lines.append("## Trades only control took (up to 10)")
        lines.append("")
        lines.append("| Date | Ticker | Side | Reasoning |")
        lines.append("| --- | --- | --- | --- |")
        for t in only_c:
            reason = (t.reasoning or "").replace("\n", " ").replace("|", "\\|")[:160]
            lines.append(f"| {t.date} | {t.ticker} | {t.side} | {reason} |")
        lines.append("")

    # A handful of reasoning samples from each arm.
    def _sample_reasoning(rows: list[SimulationTrade], n: int = 5):
        out = []
        for t in rows[:n]:
            reason = (t.reasoning or "").replace("\n", " ").strip()
            out.append(f"- {t.date} {t.side} {t.ticker}: {reason[:220]}")
        return out

    lines.append("## Reasoning samples")
    lines.append("")
    lines.append("**Treatment:**")
    lines.extend(_sample_reasoning(t_trades) or ["- (no trades)"])
    lines.append("")
    lines.append("**Control:**")
    lines.extend(_sample_reasoning(c_trades) or ["- (no trades)"])

    (run_dir / "per_profile" / f"{profile_name}.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _generate_narrative(pairs: list[PairMetrics], settings) -> str:
    """Ask Groq for a plain-language summary. Returns fallback on error."""
    if not settings.GROQ_API_KEY:
        return "_(Groq narrative skipped — no GROQ_API_KEY configured.)_"

    try:
        from langchain_groq import ChatGroq

        llm = ChatGroq(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0.3,
            streaming=False,
        )
        pair_rows = []
        for p in pairs:
            pair_rows.append(
                {
                    "profile": p.profile,
                    "treatment_return_pct": round(p.treatment_return, 2),
                    "control_return_pct": round(p.control_return, 2),
                    "return_lift_pct": round(p.return_lift_pct, 2),
                    "treatment_sharpe": (
                        round(p.treatment_sharpe, 3) if p.treatment_sharpe is not None else None
                    ),
                    "control_sharpe": (
                        round(p.control_sharpe, 3) if p.control_sharpe is not None else None
                    ),
                    "sharpe_lift": (
                        round(p.sharpe_lift, 3) if p.sharpe_lift is not None else None
                    ),
                    "treatment_max_dd_pct": round(p.treatment_max_dd, 2),
                    "control_max_dd_pct": round(p.control_max_dd, 2),
                    "treatment_trades": p.treatment_trades,
                    "control_trades": p.control_trades,
                }
            )

        system = (
            "You are a quantitative analyst writing a concise, factual "
            "summary of a historical backtest that compares trader agents "
            "that saw sentiment-tool output (treatment) against identical "
            "agents that only saw price data (control). Stick to the data "
            "provided. Be honest about where the tool didn't help."
        )
        user = (
            "Head-to-head results (JSON follows). For each profile, 'lift' "
            "is treatment minus control. Write a 4-7 sentence summary that "
            "explicitly answers:\n"
            "1) Which profiles benefited from the sentiment tool and by how much?\n"
            "2) Where did the tool hurt?\n"
            "3) What does this suggest about when the tool's signal is useful?\n"
            "4) Any caveats (trade counts, drawdowns).\n\n"
            f"{json.dumps(pair_rows, indent=2)}"
        )
        result = llm.invoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        text = getattr(result, "content", None) or str(result)
        return text.strip()
    except Exception as exc:
        logger.warning("Groq narrative generation failed: %s", exc)
        return "_(Groq narrative failed to generate; see logs.)_"


def _write_briefing_samples(
    run_dir: Path,
    run: SimulationRun,
    trading_days: list[date_cls],
    session: Session,
) -> None:
    """Emit a couple of paired briefings so you can audit exactly what
    the two arms saw on the same day.
    """
    if not trading_days or not run.universe:
        return
    # Pick three dates: near the start, middle, and end.
    idxs = sorted(
        {
            min(len(trading_days) - 1, 1),
            len(trading_days) // 2,
            len(trading_days) - 1,
        }
    )
    blocks = []
    universe = list(run.universe)
    for idx in idxs:
        cutoff = trading_days[idx - 1] if idx > 0 else trading_days[idx]
        try:
            t_brief = build_briefing(cutoff, universe, session, "treatment")
            c_brief = build_briefing(cutoff, universe, session, "control")
        except Exception as exc:
            logger.warning("Briefing sample for %s failed: %s", cutoff, exc)
            continue
        blocks.append(
            f"## Briefing as-of {cutoff}\n\n"
            f"### Treatment\n\n```json\n{json.dumps(t_brief, indent=2, default=str)}\n```\n\n"
            f"### Control\n\n```json\n{json.dumps(c_brief, indent=2, default=str)}\n```\n"
        )
    (run_dir / "briefing_samples.md").write_text(
        "# Paired briefing samples\n\n" + "\n\n".join(blocks), encoding="utf-8"
    )


def write_run_reports(
    run_id: int,
    run: SimulationRun,
    agents: list[dict],
    trading_days: list[date_cls],
    session: Session,
    settings,
) -> dict:
    """Write every artefact for the run and return a summary dict.

    The returned dict is used by the engine to populate
    ``SimulationRun.report_path`` and ``SimulationRun.final_metrics``.
    """
    run_dir = _run_dir(run_id, settings.SIMULATION_OUTPUT_DIR)

    # Preload trades per agent in a single query.
    agent_ids = [a["agent_id"] for a in agents]
    all_trades = (
        session.query(SimulationTrade)
        .filter(SimulationTrade.agent_id.in_(agent_ids))
        .order_by(SimulationTrade.agent_id, SimulationTrade.date, SimulationTrade.trade_id)
        .all()
    )
    trades_by_agent: dict[int, list[SimulationTrade]] = {aid: [] for aid in agent_ids}
    for t in all_trades:
        trades_by_agent.setdefault(t.agent_id, []).append(t)

    agents_by_key: dict[tuple[str, str], dict] = {
        (a["profile"], a["variant"]): a for a in agents
    }

    # Per-trader artefacts.
    for a in agents:
        _write_per_trader(run_dir, a, trades_by_agent.get(a["agent_id"], []), trading_days)

    # Per-profile head-to-head.
    pairs: list[PairMetrics] = []
    for profile_name in {a["profile"] for a in agents}:
        t = agents_by_key.get((profile_name, "treatment"))
        c = agents_by_key.get((profile_name, "control"))
        if not t or not c:
            continue
        pair = pair_metrics(
            profile=profile_name,
            treatment_equity=t["equity_curve"],
            control_equity=c["equity_curve"],
            treatment_metrics=t["metrics"],
            control_metrics=c["metrics"],
        )
        pairs.append(pair)
        _write_per_profile(run_dir, profile_name, t, c, trades_by_agent, pair)

    pairs.sort(key=lambda p: p.return_lift_pct, reverse=True)

    # Aggregate + leaderboard.
    leaderboard = sorted(
        agents,
        key=lambda a: a["metrics"].total_return_pct,
        reverse=True,
    )

    lines = [
        f"# Simulation run {run_id}",
        "",
        f"- Dates: {run.start_date} → {run.end_date}",
        f"- Universe ({len(run.universe or [])} tickers): {', '.join(run.universe or [])}",
        f"- Starting cash per agent: ${(run.config or {}).get('starting_cash', 1000):.2f}",
        f"- Groq model: {(run.config or {}).get('groq_model', '—')}",
        f"- Profiles: {', '.join((run.config or {}).get('profiles', []))}",
        "",
        "## Leaderboard (all agents)",
        "",
        "| Rank | Profile | Variant | Return | Sharpe | Max DD | Trades | Final equity |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, a in enumerate(leaderboard, start=1):
        m: AgentMetrics = a["metrics"]
        lines.append(
            f"| {rank} | {a['profile']} | {a['variant']} | "
            f"{_fmt_pct(m.total_return_pct)} | {_fmt_num(m.sharpe, 3)} | "
            f"{_fmt_pct(m.max_drawdown_pct)} | {m.trade_count} | "
            f"{_money(m.final_equity)} |"
        )

    lines.extend([
        "",
        "## Head-to-head (treatment − control) by profile",
        "",
        "| Profile | Return lift | Sharpe lift | Max-DD delta | Trade delta | Equity corr. |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for p in pairs:
        lines.append(
            f"| {p.profile} | {_fmt_pct(p.return_lift_pct)} | "
            f"{_fmt_num(p.sharpe_lift, 3)} | {_fmt_pct(p.max_dd_delta)} | "
            f"{p.treatment_trades - p.control_trades:+d} | "
            f"{_fmt_num(p.equity_correlation, 3)} |"
        )

    lines.extend(["", "## Equity sparklines", ""])
    for a in leaderboard:
        lines.append(
            f"- `{_sparkline(a['equity_curve'])}` {a['profile']}/{a['variant']} → "
            f"{_money(a['metrics'].final_equity)}"
        )

    narrative = _generate_narrative(pairs, settings)
    lines.extend(["", "## Narrative summary", "", narrative])

    (run_dir / "run_summary.md").write_text("\n".join(lines), encoding="utf-8")

    summary_json = {
        "run_id": run_id,
        "start_date": str(run.start_date),
        "end_date": str(run.end_date),
        "universe": run.universe,
        "config": run.config,
        "leaderboard": [
            {
                "profile": a["profile"],
                "variant": a["variant"],
                "total_return_pct": a["metrics"].total_return_pct,
                "sharpe": a["metrics"].sharpe,
                "max_drawdown_pct": a["metrics"].max_drawdown_pct,
                "trade_count": a["metrics"].trade_count,
                "final_equity": a["metrics"].final_equity,
            }
            for a in leaderboard
        ],
        "pairs": [
            {
                "profile": p.profile,
                "treatment_return_pct": p.treatment_return,
                "control_return_pct": p.control_return,
                "return_lift_pct": p.return_lift_pct,
                "treatment_sharpe": p.treatment_sharpe,
                "control_sharpe": p.control_sharpe,
                "sharpe_lift": p.sharpe_lift,
                "treatment_max_dd_pct": p.treatment_max_dd,
                "control_max_dd_pct": p.control_max_dd,
                "max_dd_delta": p.max_dd_delta,
                "treatment_trades": p.treatment_trades,
                "control_trades": p.control_trades,
                "equity_correlation": p.equity_correlation,
            }
            for p in pairs
        ],
        "narrative": narrative,
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary_json, default=str, indent=2),
        encoding="utf-8",
    )

    _write_briefing_samples(run_dir, run, trading_days, session)

    return {
        "report_path": str(run_dir),
        "final_metrics": {
            "leaderboard": summary_json["leaderboard"],
            "pairs": summary_json["pairs"],
        },
    }
