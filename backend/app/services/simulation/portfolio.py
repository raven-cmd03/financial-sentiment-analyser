"""Pure-function portfolio accounting for the backtest simulation.

The engine is the only stateful component. Everything here takes a
portfolio snapshot + an order list + a price map and returns a new
snapshot plus the executed trades. No DB access, no side effects —
which is what makes the engine trivially testable.

Conventions:
- Cash is always ``float`` (USD). Fractional shares are allowed so $1000
  of starting capital is actually spendable on $300+ tickers.
- Long only: any ``sell`` that would push holdings negative is truncated
  to whatever the agent currently holds. A buy that can't fit is rejected.
- ``size_pct`` is in the range 0-1 and applies to *current cash* for buys
  and *current holdings of that ticker* for sells.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class Order:
    ticker: str
    side: Side
    size_pct: float
    reasoning: str = ""


@dataclass
class Portfolio:
    cash: float
    # {ticker: shares}. Fractional values permitted.
    holdings: dict[str, float] = field(default_factory=dict)

    def copy(self) -> "Portfolio":
        return Portfolio(cash=self.cash, holdings=dict(self.holdings))

    def equity(self, prices: dict[str, float]) -> float:
        total = self.cash
        for ticker, shares in self.holdings.items():
            px = prices.get(ticker)
            if px is not None and shares:
                total += shares * px
        return total


@dataclass(frozen=True)
class ExecutedTrade:
    ticker: str
    side: Side
    shares: float
    price: float
    cash_after: float
    equity_after: float
    reasoning: str
    # Why a submitted order was truncated/rejected, if anything went wrong.
    note: str = ""


def apply_orders(
    portfolio: Portfolio,
    orders: list[Order],
    prices: dict[str, float],
    universe: set[str],
) -> tuple[Portfolio, list[ExecutedTrade], list[str]]:
    """Apply ``orders`` against ``portfolio`` using ``prices``.

    Returns the *new* portfolio, the list of executed trades, and a list
    of human-readable rejection messages for anything that was dropped
    (used by the engine for logging; never raises).

    Orders are processed in the given order — a sell frees cash for a
    subsequent buy, which is usually what the LLM intends when it
    returns a sequence.
    """
    p = portfolio.copy()
    executed: list[ExecutedTrade] = []
    rejections: list[str] = []

    for order in orders:
        ticker = (order.ticker or "").upper().strip()
        if not ticker:
            rejections.append("empty ticker skipped")
            continue
        if ticker not in universe:
            rejections.append(f"{ticker} not in universe — skipped")
            continue

        price = prices.get(ticker)
        if price is None or price <= 0:
            rejections.append(f"{ticker} has no usable open price — skipped")
            continue

        size_pct = order.size_pct
        try:
            size_pct = float(size_pct)
        except (TypeError, ValueError):
            rejections.append(f"{ticker} size_pct not numeric — skipped")
            continue
        # Clamp to [0, 1]. An LLM asking for 150% of cash is capped at
        # 100%, a 0% order is a no-op, negative orders are no-ops too.
        if size_pct <= 0:
            continue
        if size_pct > 1.0:
            size_pct = 1.0

        if order.side == "buy":
            spend = p.cash * size_pct
            if spend <= 0:
                continue
            shares = spend / price
            if shares <= 0:
                continue
            p.cash -= spend
            p.holdings[ticker] = p.holdings.get(ticker, 0.0) + shares
            equity_after = p.equity(prices)
            executed.append(
                ExecutedTrade(
                    ticker=ticker,
                    side="buy",
                    shares=shares,
                    price=price,
                    cash_after=p.cash,
                    equity_after=equity_after,
                    reasoning=order.reasoning or "",
                )
            )

        elif order.side == "sell":
            current = p.holdings.get(ticker, 0.0)
            if current <= 0:
                rejections.append(f"{ticker} sell rejected — no holdings")
                continue
            shares_to_sell = current * size_pct
            if shares_to_sell <= 0:
                continue
            proceeds = shares_to_sell * price
            p.cash += proceeds
            remaining = current - shares_to_sell
            # Avoid lingering dust rows.
            if remaining <= 1e-9:
                p.holdings.pop(ticker, None)
            else:
                p.holdings[ticker] = remaining
            equity_after = p.equity(prices)
            executed.append(
                ExecutedTrade(
                    ticker=ticker,
                    side="sell",
                    shares=shares_to_sell,
                    price=price,
                    cash_after=p.cash,
                    equity_after=equity_after,
                    reasoning=order.reasoning or "",
                )
            )

        else:
            rejections.append(f"{ticker} unknown side {order.side!r} — skipped")
            continue

    return p, executed, rejections
