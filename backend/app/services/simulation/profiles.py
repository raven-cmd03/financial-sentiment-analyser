"""Trader-agent profiles for the backtest simulation.

Each profile declares:

- ``name``: stable identifier, used in DB rows and report paths.
- ``cadence_days``: how often (in trading days) the agent is prompted.
  1 = every trading day; 7 = once per trading week; etc.
- ``display_name`` + ``description``: human-readable blurb used in reports.
- ``system_prompt``: personality/strategy baked into every LLM call. The
  *same* prompt is used for both ``treatment`` and ``control`` variants
  so the only independent variable is the briefing payload.

Profiles are plain dataclasses so adding a new one is a two-line change:
append to ``TRADER_PROFILES`` and the engine will automatically spin up
one treatment + one control instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Variant = Literal["treatment", "control"]

VARIANTS: tuple[Variant, Variant] = ("treatment", "control")


@dataclass(frozen=True)
class TraderProfile:
    name: str
    display_name: str
    description: str
    cadence_days: int
    system_prompt: str
    # Some profiles (``news_driven``) trigger on tool-specific signals that
    # don't exist in the control arm. When set, ``control_trigger_hint`` is
    # appended to the *control* briefing so the agent has a price-only
    # analogue to act on instead of silently waiting forever.
    control_trigger_hint: str | None = None


_DISCLAIMER = (
    "You are participating in a historical backtest simulation with $1000 of "
    "starting capital. You are allowed to go long only (no shorts), fractional "
    "shares are allowed, there is zero commission and zero slippage. On each "
    "decision day you may issue buy or sell orders as a percentage of current "
    "cash (for buys) or current holdings (for sells). You must never look at "
    "data dated after the briefing date, and you must only trade tickers listed "
    "in the briefing's universe. Always return a structured JSON order list; "
    "an empty list means 'do nothing today'."
)


_PROFILES: list[TraderProfile] = [
    TraderProfile(
        name="day_trader",
        display_name="Day Trader",
        cadence_days=1,
        description=(
            "Aggressive intraday-style trader. Intended max hold ~1 day. "
            "Acts on short-term momentum — and, in the treatment arm, on "
            "same-day sentiment spikes."
        ),
        system_prompt=(
            "You are an aggressive day trader. You care about short-term momentum "
            "over the last 1-3 trading days and intraday catalysts. Typical hold "
            "period is under 1-2 days. You size positions at 10-30% of cash per "
            "trade and you are happy to rotate capital daily. You cut losers fast. "
            "If the briefing contains sentiment data, treat a sharp positive spike "
            "as bullish confirmation of a price up-move and a sharp negative spike "
            "as a reason to exit. If the briefing only has price data, rely purely "
            "on price and volume action. " + _DISCLAIMER
        ),
    ),
    TraderProfile(
        name="swing_trader",
        display_name="Swing Trader",
        cadence_days=3,
        description=(
            "3-10 day holds. Reacts to 7-day price-trend shifts — and, in the "
            "treatment arm, to sentiment-trend shifts."
        ),
        system_prompt=(
            "You are a swing trader. You target 3-10 day holds and you act on "
            "multi-day trend shifts, pullback entries, and momentum continuations. "
            "Typical position size is 15-35% of cash per name. You ignore "
            "day-to-day noise and focus on the 7-day price trend. In the treatment "
            "arm you also look at the 7-day sentiment trend as a confirmation "
            "signal; in the control arm you rely entirely on price, volume, and "
            "20-day volatility. " + _DISCLAIMER
        ),
    ),
    TraderProfile(
        name="momentum_investor",
        display_name="Momentum Investor",
        cadence_days=7,
        description=(
            "Holds while trends persist upward. Treatment requires sentiment "
            "agreement; control trusts price momentum alone."
        ),
        system_prompt=(
            "You are a momentum investor. You buy names whose 7-day and 30-day "
            "returns are both positive and you hold as long as the trend persists. "
            "You exit when momentum rolls over. You typically run 3-6 positions at "
            "20-40% each. In the treatment arm, do NOT buy a new name unless "
            "sentiment is at least neutral-to-positive; flag sentiment/price "
            "divergences as exit triggers. In the control arm, work purely off "
            "price momentum and volatility. " + _DISCLAIMER
        ),
    ),
    TraderProfile(
        name="contrarian",
        display_name="Contrarian",
        cadence_days=7,
        description=(
            "Fades extreme moves. Treatment also fades sentiment extremes; "
            "control fades price extremes only."
        ),
        system_prompt=(
            "You are a contrarian trader. You fade extreme moves and buy oversold "
            "names. You look for sharp drawdowns (>10% from recent high), elevated "
            "volatility, and capitulation signals. In the treatment arm, you also "
            "fade extreme negative sentiment — a very bearish sentiment reading on "
            "a name that's already down a lot is your buy signal, and extreme "
            "positive sentiment on a name at highs is your sell signal. In the "
            "control arm, fade price extremes only (e.g. 2-stddev moves vs 20-day "
            "baseline). Position size 10-25% per name. " + _DISCLAIMER
        ),
    ),
    TraderProfile(
        name="news_driven",
        display_name="News-Driven Trader",
        cadence_days=1,
        description=(
            "Treatment acts on sentiment events (pos/neg swings); control has no "
            "news feed and falls back to 2-stddev price moves as its proxy event."
        ),
        system_prompt=(
            "You are a news-driven trader. You only act when there's a clear "
            "event on a name — otherwise you sit in cash. In the treatment arm an "
            "event is a large swing in the daily sentiment rollup, a sudden spike "
            "in article volume, or a strongly bullish/bearish headline. In the "
            "control arm — where you receive no news or sentiment data — an event "
            "is defined as a ~2-stddev daily price move vs the name's 20-day "
            "history. Your position sizes are 15-30% and you typically hold for "
            "3-7 days after entering on an event. " + _DISCLAIMER
        ),
        control_trigger_hint=(
            "You have no news feed in this arm. Treat a daily return that deviates "
            "by roughly 2 standard deviations or more from the ticker's 20-day "
            "baseline as your 'event' trigger."
        ),
    ),
    TraderProfile(
        name="value_investor",
        display_name="Value Investor",
        cadence_days=30,
        description=(
            "Low turnover, long bias. Treatment bias: sustained negative "
            "sentiment on otherwise healthy names. Control bias: names down "
            ">15% from their 30-day high."
        ),
        system_prompt=(
            "You are a patient, low-turnover value investor. You think monthly, "
            "you hold for weeks to months, and you run concentrated 3-5 position "
            "books at 20-40% per name. You are looking for mispriced names. In the "
            "treatment arm, you lean into tickers with sustained negative "
            "sentiment over the last month (which you treat as an over-reaction). "
            "In the control arm, you lean into tickers that are down >15% from "
            "their trailing 30-day high and whose 30-day return is the most "
            "negative in the universe. You rarely sell — only on a clear thesis "
            "break or to rebalance. " + _DISCLAIMER
        ),
    ),
]


TRADER_PROFILES: dict[str, TraderProfile] = {p.name: p for p in _PROFILES}


def get_profile(name: str) -> TraderProfile:
    """Return the profile with the given name. Raises ``KeyError`` if unknown."""
    if name not in TRADER_PROFILES:
        raise KeyError(
            f"Unknown trader profile {name!r}. "
            f"Known profiles: {sorted(TRADER_PROFILES)}"
        )
    return TRADER_PROFILES[name]


def list_profiles() -> list[TraderProfile]:
    """Return all registered profiles in declaration order."""
    return list(TRADER_PROFILES.values())
