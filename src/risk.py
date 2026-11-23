"""Hard risk rules. Enforced in code so no AI model can talk its way past them.

Change the numbers here (or via env vars), not in prompts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

MAX_POSITION_PCT = float(os.getenv("RISK_MAX_POSITION_PCT", "5"))   # % of portfolio per idea
MAX_STOP_DISTANCE_PCT = float(os.getenv("RISK_MAX_STOP_PCT", "15")) # stop can't be further than this
MIN_PRICE = float(os.getenv("RISK_MIN_PRICE", "5"))                 # no penny stocks
MIN_MARKET_CAP = float(os.getenv("RISK_MIN_MARKET_CAP", "300e6"))   # manipulation risk below this
MAX_IDEAS_PER_WEEK = int(os.getenv("RISK_MAX_IDEAS_PER_WEEK", "5")) # stops over-trading
ALLOWED_SIDES = {"buy", "sell", "trim"}  # no shorting, options or leverage


@dataclass
class RiskCheck:
    approved: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check(side: str, position_pct: float, price: float | None, stop: float | None,
          market_cap: float | None, ideas_this_week: int) -> RiskCheck:
    side = side.lower().strip()
    v, w = [], []
    if side not in ALLOWED_SIDES:
        v.append(f"side '{side}' not allowed (only {sorted(ALLOWED_SIDES)}; no shorts, options or leverage)")
    if side == "buy":
        if not 0 < position_pct <= MAX_POSITION_PCT:
            v.append(f"position {position_pct}% outside 0–{MAX_POSITION_PCT}% of portfolio")
        if price is None:
            v.append("current price unknown")
        elif price < MIN_PRICE:
            v.append(f"price ${price:.2f} below ${MIN_PRICE:.0f} minimum (penny-stock risk)")
        if market_cap is None:
            w.append("market cap unknown; couldn't check manipulation risk")
        elif market_cap < MIN_MARKET_CAP:
            v.append(f"market cap ${market_cap / 1e6:,.0f}M below ${MIN_MARKET_CAP / 1e6:,.0f}M minimum")
        if stop is None or stop <= 0:
            v.append("every buy needs a stop-loss price")
        elif price:
            if stop >= price:
                v.append("stop must be below the current price")
            elif (price - stop) / price * 100 > MAX_STOP_DISTANCE_PCT:
                v.append(f"stop is {(price - stop) / price * 100:.1f}% away; max {MAX_STOP_DISTANCE_PCT}%")
        if ideas_this_week >= MAX_IDEAS_PER_WEEK:
            v.append(f"already {ideas_this_week} ideas logged this week (max {MAX_IDEAS_PER_WEEK})")
    return RiskCheck(approved=not v, violations=v, warnings=w)


def rules_text() -> str:
    return (f"Max {MAX_POSITION_PCT}% of portfolio per position; buys need a stop-loss within "
            f"{MAX_STOP_DISTANCE_PCT}%; no stocks under ${MIN_PRICE:.0f} or ${MIN_MARKET_CAP / 1e6:,.0f}M market cap; "
            f"no shorting, options or leverage; max {MAX_IDEAS_PER_WEEK} new ideas per week.")
