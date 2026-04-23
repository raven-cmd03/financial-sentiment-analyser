"""LLM-backed trader agent for the backtest simulation.

Wraps ``ChatGroq`` with a Pydantic-schema-enforced structured output so
a broken JSON response from the model can't corrupt the engine's
accounting. If the LLM call raises, ``decide`` returns an empty list —
the engine treats that as "hold today" and logs the failure.
"""

from __future__ import annotations

import json
import logging
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from app.services.simulation.portfolio import Order, Portfolio
from app.services.simulation.profiles import TraderProfile

logger = logging.getLogger(__name__)

Side = Literal["buy", "sell"]


class StructuredOrder(BaseModel):
    """One trade order as emitted by the LLM."""

    ticker: str = Field(
        description="Ticker symbol from the briefing universe. Will be upper-cased.",
    )
    side: Side = Field(description="'buy' or 'sell'.")
    size_pct: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Size as a fraction in [0, 1]. For buys, fraction of current cash "
            "to deploy. For sells, fraction of current holdings of the ticker "
            "to liquidate."
        ),
    )
    reasoning: str = Field(
        default="",
        description="1-2 sentence explanation referencing the briefing.",
    )

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return (v or "").strip().upper()


class OrderList(BaseModel):
    """Structured output schema the LLM must conform to."""

    orders: list[StructuredOrder] = Field(
        default_factory=list,
        description=(
            "Zero or more orders to execute on the next trading day's open. "
            "Return an empty list to hold all current positions."
        ),
    )


class _LLMLike(Protocol):
    """Minimal interface the agent needs from a langchain chat model.

    Used so the engine / tests can substitute a fake LLM without needing
    a Groq key or network.
    """

    def with_structured_output(self, schema: type[BaseModel]):  # pragma: no cover
        ...


class TraderAgent:
    """LLM trader for a single profile + variant pair."""

    def __init__(
        self,
        profile: TraderProfile,
        variant: str,
        llm: _LLMLike | None = None,
    ):
        self.profile = profile
        self.variant = variant
        self._llm = llm
        self._structured = None

    def _ensure_structured(self):
        if self._structured is None:
            if self._llm is None:
                raise RuntimeError("TraderAgent has no LLM configured")
            self._structured = self._llm.with_structured_output(OrderList)
        return self._structured

    def decide(
        self,
        briefing: dict,
        portfolio: Portfolio,
        day: str,
    ) -> list[Order]:
        """Ask the LLM what to do given a briefing + current portfolio.

        Returns a list of ``Order`` objects ready for the portfolio
        module. Any exception from the LLM is caught and results in an
        empty list — "hold today" is always a safe fallback.
        """
        prompt = self._build_prompt(briefing, portfolio, day)
        try:
            structured = self._ensure_structured()
            result: OrderList = structured.invoke(
                [
                    {"role": "system", "content": self.profile.system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )
        except Exception as exc:
            logger.warning(
                "Agent %s/%s LLM call failed on %s: %s",
                self.profile.name,
                self.variant,
                day,
                exc,
            )
            return []

        if not isinstance(result, OrderList):
            # ``with_structured_output`` should always return ``OrderList``
            # but some backends can return a dict; defensively coerce.
            try:
                result = OrderList.model_validate(result)
            except Exception:
                logger.warning(
                    "Agent %s/%s received non-OrderList response: %r",
                    self.profile.name,
                    self.variant,
                    result,
                )
                return []

        orders: list[Order] = []
        for o in result.orders:
            orders.append(
                Order(
                    ticker=o.ticker,
                    side=o.side,
                    size_pct=float(o.size_pct),
                    reasoning=o.reasoning or "",
                )
            )
        return orders

    def _build_prompt(
        self, briefing: dict, portfolio: Portfolio, day: str
    ) -> str:
        holdings_lines = []
        for t, s in sorted(portfolio.holdings.items()):
            holdings_lines.append(f"  - {t}: {s:.6f} shares")
        holdings_block = "\n".join(holdings_lines) if holdings_lines else "  (none)"

        hint = ""
        if self.variant == "control" and self.profile.control_trigger_hint:
            hint = (
                "\n\nVariant-specific hint (control arm):\n"
                f"{self.profile.control_trigger_hint}"
            )

        return (
            f"Decision day (orders fill on this day's open price): {day}\n"
            f"Your current cash: ${portfolio.cash:.2f}\n"
            f"Your current holdings:\n{holdings_block}\n\n"
            f"Briefing (as-of {briefing.get('as_of')}, variant={briefing.get('variant')}):\n"
            f"{json.dumps(briefing, indent=2, default=str)}"
            f"{hint}\n\n"
            f"Respond with a JSON object matching the OrderList schema. "
            f"Use tickers only from the briefing's universe. "
            f"Empty orders list = hold everything today."
        )
