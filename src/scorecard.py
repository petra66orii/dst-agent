"""Weekly scorecard: did the signals actually beat the benchmark?

    python -m src.scorecard
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src import ledger, market_data
from src.send_report import post
from src.settings import BENCHMARK

HORIZONS = (1, 5, 20)  # trading days
MIN_SAMPLE = 30  # below this, results are anecdotes, not evidence


def forward_returns(rows: list[dict], closes: pd.DataFrame, horizons=HORIZONS) -> pd.DataFrame:
    """One row per signal with forward returns and excess return vs the benchmark."""
    out = []
    idx = closes.index
    for r in rows:
        t, bench = r["ticker"], r.get("benchmark") or BENCHMARK
        if t not in closes or bench not in closes:
            continue
        d = pd.Timestamp(r["date"])
        pos = idx.searchsorted(d, side="right") - 1  # last trading day on/before signal date
        if pos < 0:
            continue
        rec = {"date": r["date"], "ticker": t, "signal": r["signal"], "score": float(r["score"]),
               "momentum": float(r["momentum"]), "insider": float(r["insider"]), "news": float(r["news"])}
        p0, b0 = closes[t].iloc[pos], closes[bench].iloc[pos]
        for h in horizons:
            if pos + h < len(idx) and pd.notna(p0) and pd.notna(b0):
                ret = closes[t].iloc[pos + h] / p0 - 1
                bret = closes[bench].iloc[pos + h] / b0 - 1
                rec[f"ret_{h}d"] = ret
                rec[f"excess_{h}d"] = ret - bret
            else:
                rec[f"ret_{h}d"] = rec[f"excess_{h}d"] = None
        out.append(rec)
    return pd.DataFrame(out)


def summarise(df: pd.DataFrame, horizons=HORIZONS) -> dict:
    res = {"by_signal": {}, "components": {}, "spread": {}}
    if df.empty:
        return res
    for sig in ("Buy", "Hold", "Sell"):
        sub = df[df["signal"] == sig]
        res["by_signal"][sig] = {}
        for h in horizons:
            ex = sub[f"excess_{h}d"].dropna().astype(float)
            if ex.empty:
                continue
            # A Sell "wins" if the stock lagged the benchmark.
            wins = (ex < 0).mean() if sig == "Sell" else (ex > 0).mean()
            res["by_signal"][sig][h] = {"n": int(len(ex)), "avg_excess": float(ex.mean()), "hit_rate": float(wins)}
    for h in horizons:
        col = f"excess_{h}d"
        valid = df.dropna(subset=[col])
        buys = valid[valid["signal"] == "Buy"][col].astype(float)
        sells = valid[valid["signal"] == "Sell"][col].astype(float)
        if len(buys) and len(sells):
            res["spread"][h] = float(buys.mean() - sells.mean())
        if len(valid) >= MIN_SAMPLE:
            # Rank correlation between each component and what happened next (information coefficient).
            res["components"][h] = {
                c: float(valid[c].rank().corr(valid[col].astype(float).rank()))
                for c in ("score", "momentum", "insider", "news")
                if valid[c].nunique() > 1
            }
    return res


def format_scorecard(summary: dict, n_signals: int, since: str) -> str:
    pct = lambda x: f"{x * 100:+.2f}%"
    lines = [f"🧾 **DST Scorecard** — {n_signals} signals since {since} (excess return vs {BENCHMARK})"]
    if n_signals < MIN_SAMPLE:
        lines.append(f"⚠️ Only {n_signals} signals so far; treat anything below as noise until ~{MIN_SAMPLE}+.")
    for sig, by_h in summary["by_signal"].items():
        if not by_h:
            continue
        parts = [f"{h}d {pct(v['avg_excess'])} ({v['hit_rate'] * 100:.0f}% hit, n={v['n']})" for h, v in by_h.items()]
        lines.append(f"• **{sig}**: " + " · ".join(parts))
    if summary["spread"]:
        lines.append("• **Buy − Sell spread**: " + " · ".join(f"{h}d {pct(v)}" for h, v in summary["spread"].items()))
    if summary["components"]:
        lines.append("\n**Which inputs predict returns?** (rank correlation, >0.05 is useful, <0 is harmful)")
        for h, comps in summary["components"].items():
            lines.append(f"• {h}d: " + ", ".join(f"{k} {v:+.2f}" for k, v in comps.items()))
    lines.append("\n_Verdict rule: only consider real money once Buy beats the benchmark at 20d over 3+ months "
                 "and 100+ signals, after costs._")
    return "\n".join(lines)


def run(lookback_days: int = 365) -> str:
    rows = ledger.read()
    cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    rows = [r for r in rows if r["date"] >= cutoff]
    if not rows:
        msg = "🧾 **DST Scorecard** — no signals recorded yet."
        post(msg)
        return msg
    since = min(r["date"] for r in rows)
    tickers = {r["ticker"] for r in rows} | {r.get("benchmark") or BENCHMARK for r in rows}
    start = (pd.Timestamp(since) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    closes = market_data.get_closes(sorted(tickers), start=start)
    df = forward_returns(rows, closes)
    msg = format_scorecard(summarise(df), len(rows), since)
    post(msg)
    return msg


if __name__ == "__main__":
    print(run())
