"""Metrics + head-to-head helpers for simulation reporting."""

from __future__ import annotations

import math
from dataclasses import dataclass


_TRADING_DAYS = 252


@dataclass(frozen=True)
class AgentMetrics:
    total_return_pct: float
    annualised_return_pct: float | None
    sharpe: float | None
    max_drawdown_pct: float
    trade_count: int
    win_rate: float | None
    final_equity: float
    starting_equity: float


@dataclass(frozen=True)
class PairMetrics:
    profile: str
    treatment_return: float
    control_return: float
    return_lift_pct: float  # treatment - control, both in %
    treatment_sharpe: float | None
    control_sharpe: float | None
    sharpe_lift: float | None
    treatment_max_dd: float
    control_max_dd: float
    max_dd_delta: float
    treatment_trades: int
    control_trades: int
    equity_correlation: float | None


def _daily_returns(equity: list[float]) -> list[float]:
    rets = []
    for i in range(1, len(equity)):
        prev = equity[i - 1]
        if prev and prev != 0:
            rets.append((equity[i] - prev) / prev)
    return rets


def _sharpe(rets: list[float]) -> float | None:
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd == 0:
        return None
    return (mean / sd) * math.sqrt(_TRADING_DAYS)


def _max_drawdown(equity: list[float]) -> float:
    if not equity:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return max_dd  # negative or zero


def compute_agent_metrics(
    equity_curve: list[float],
    trade_count: int,
    realised_pnls: list[float] | None = None,
) -> AgentMetrics:
    """Compute standard performance metrics from a daily equity curve.

    ``equity_curve`` should be the total-equity value at end of day,
    oldest-first. ``realised_pnls`` is optional and only used to compute
    win-rate; when omitted win-rate is ``None``.
    """
    if not equity_curve:
        return AgentMetrics(
            total_return_pct=0.0,
            annualised_return_pct=None,
            sharpe=None,
            max_drawdown_pct=0.0,
            trade_count=trade_count,
            win_rate=None,
            final_equity=0.0,
            starting_equity=0.0,
        )

    start = equity_curve[0]
    final = equity_curve[-1]
    total_return = (final - start) / start if start else 0.0

    rets = _daily_returns(equity_curve)
    ann_ret = None
    if len(rets) >= 2:
        ann_ret = ((1 + total_return) ** (_TRADING_DAYS / max(len(rets), 1))) - 1

    sharpe = _sharpe(rets)
    max_dd = _max_drawdown(equity_curve)

    win_rate = None
    if realised_pnls:
        wins = sum(1 for x in realised_pnls if x > 0)
        win_rate = wins / len(realised_pnls)

    return AgentMetrics(
        total_return_pct=total_return * 100.0,
        annualised_return_pct=(ann_ret * 100.0) if ann_ret is not None else None,
        sharpe=sharpe,
        max_drawdown_pct=max_dd * 100.0,
        trade_count=trade_count,
        win_rate=win_rate,
        final_equity=final,
        starting_equity=start,
    )


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    xs = xs[:n]
    ys = ys[:n]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    dy = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def pair_metrics(
    profile: str,
    treatment_equity: list[float],
    control_equity: list[float],
    treatment_metrics: AgentMetrics,
    control_metrics: AgentMetrics,
) -> PairMetrics:
    """Head-to-head summary for a treatment + control pair."""
    sharpe_lift = None
    if treatment_metrics.sharpe is not None and control_metrics.sharpe is not None:
        sharpe_lift = treatment_metrics.sharpe - control_metrics.sharpe

    return PairMetrics(
        profile=profile,
        treatment_return=treatment_metrics.total_return_pct,
        control_return=control_metrics.total_return_pct,
        return_lift_pct=treatment_metrics.total_return_pct - control_metrics.total_return_pct,
        treatment_sharpe=treatment_metrics.sharpe,
        control_sharpe=control_metrics.sharpe,
        sharpe_lift=sharpe_lift,
        treatment_max_dd=treatment_metrics.max_drawdown_pct,
        control_max_dd=control_metrics.max_drawdown_pct,
        max_dd_delta=treatment_metrics.max_drawdown_pct - control_metrics.max_drawdown_pct,
        treatment_trades=treatment_metrics.trade_count,
        control_trades=control_metrics.trade_count,
        equity_correlation=_pearson(treatment_equity, control_equity),
    )
