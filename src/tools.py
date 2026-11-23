"""Tools shared by the MCP connector and the Discord agent.

Every function returns plain JSON-serialisable data and never raises: errors come back as
{"error": ...} so the model can say what it couldn't get instead of inventing it.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from src import edgar, market_data, repo_data, risk
from src.news_scraper import get_stock_news
from src.settings import BENCHMARK

IDEAS_PATH = "data/agent_ideas.csv"
IDEA_FIELDS = ["logged_at", "ticker", "side", "position_pct", "entry_price", "stop", "target",
               "horizon_days", "thesis", "invalidation", "sources", "model"]


def safe(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
    return wrapper


def _ticker(t: str) -> str:
    t = (t or "").upper().strip()
    if not t or len(t) > 6 or not t.replace(".", "").replace("-", "").isalnum():
        raise ValueError(f"invalid ticker {t!r}")
    return t


# ------------------------------------------------------------------ bot data (from repo)

@safe
def get_watchlist() -> dict:
    """Tickers the daily job analyses."""
    text = repo_data.read_text("data/stocks.json")
    return {"tickers": json.loads(text) if text else [], "benchmark": BENCHMARK}


@safe
def get_latest_signals(ticker: str = "") -> dict:
    """Most recent daily report (all tickers, or one)."""
    logs = [f for f in repo_data.list_dir("logs") if f.startswith("dst_") and f.endswith(".json")]
    if not logs:
        return {"error": "no daily reports yet"}
    report = json.loads(repo_data.read_text(f"logs/{logs[-1]}"))
    signals = report.get("signals", [])
    if ticker:
        t = _ticker(ticker)
        signals = [s for s in signals if s.get("ticker") == t]
        if not signals:
            return {"date": report.get("date"), "error": f"{t} not in the latest report"}
    for s in signals:  # trim bulky fields
        s.pop("headlines", None)
    return {"date": report.get("date"), "benchmark": report.get("benchmark"),
            "buy": report.get("buy"), "sell": report.get("sell"), "hold": report.get("hold"),
            "signals": signals}


def _ledger_rows() -> list[dict]:
    text = repo_data.read_text("data/signals.csv")
    return list(csv.DictReader(io.StringIO(text))) if text else []


@safe
def get_signal_history(ticker: str, days: int = 60) -> dict:
    """Past daily signals for one ticker from the ledger."""
    t = _ticker(ticker)
    cutoff = (date.today() - timedelta(days=int(days))).isoformat()
    rows = [r for r in _ledger_rows() if r["ticker"] == t and r["date"] >= cutoff]
    return {"ticker": t, "rows": rows[-120:]}


@safe
def get_scorecard(lookback_days: int = 365) -> dict:
    """How past signals performed vs the benchmark (1/5/20 trading days)."""
    from src import scorecard
    import pandas as pd

    cutoff = (date.today() - timedelta(days=int(lookback_days))).isoformat()
    rows = [r for r in _ledger_rows() if r["date"] >= cutoff]
    if not rows:
        return {"error": "no signals recorded yet"}
    since = min(r["date"] for r in rows)
    tickers = {r["ticker"] for r in rows} | {r.get("benchmark") or BENCHMARK for r in rows}
    start = (pd.Timestamp(since) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    closes = market_data.get_closes(sorted(tickers), start=start)
    summary = scorecard.summarise(scorecard.forward_returns(rows, closes))
    return {"n_signals": len(rows), "since": since, "min_sample_for_evidence": scorecard.MIN_SAMPLE,
            "summary": json.loads(json.dumps(summary, default=str))}


# ------------------------------------------------------------------ live data

@safe
def get_price_summary(ticker: str) -> dict:
    """Latest close, 1d/20d returns, relative strength vs benchmark, MA regime, volatility, market cap."""
    t = _ticker(ticker)
    closes = market_data.get_closes([t, BENCHMARK], period="1y")
    if t not in closes:
        return {"error": f"no price data for {t}"}
    feats = market_data.price_features(closes[t], closes[BENCHMARK])
    feats["trend_score"] = market_data.score_momentum(feats)
    feats["as_of"] = str(closes.index[-1].date())
    feats["market_cap"] = market_data.get_market_cap(t)
    return {"ticker": t, "benchmark": BENCHMARK, **feats}


@safe
def get_recent_filings(ticker: str, days: int = 30, forms: str = "8-K,10-Q,10-K,SC 13D,SC 13G") -> dict:
    """SEC filings with links; 8-Ks include item labels (e.g. 5.02 executive change)."""
    t = _ticker(ticker)
    cik = edgar.get_cik(t)
    if not cik:
        return {"error": f"no SEC CIK for {t}"}
    wanted = {f.strip() for f in forms.split(",") if f.strip()}
    wanted |= {f + "/A" for f in wanted}
    out = []
    for f in edgar.recent_filings(cik, wanted, date.today() - timedelta(days=int(days)))[:25]:
        out.append({"form": f["form"], "filed": f["filed"],
                    "items": [f"{i} {edgar.EIGHT_K_ITEMS.get(i, '')}".strip() for i in f["items"]],
                    "url": edgar.filing_url(cik, f["accession"], f["primary_doc"])})
    return {"ticker": t, "filings": out}


@safe
def get_insider_activity(ticker: str, days: int = 90) -> dict:
    """Open-market insider buys/sells by officers and directors (Form 4), excluding grants,
    option exercises, tax withholding and 10b5-1 planned sales."""
    t = _ticker(ticker)
    s = edgar.insider_activity(t, days=int(days))
    s["insider_score"] = edgar.score_insiders(s)
    return s


@safe
def get_news(ticker: str, limit: int = 10) -> dict:
    """Recent headlines, each tagged verified_source (tier-1 outlet / wire service) or not.
    Unverified headlines must not be treated as fact."""
    t = _ticker(ticker)
    items = get_stock_news(t, limit=min(int(limit), 20))
    for i in items:
        i["published"] = datetime.fromtimestamp(i.pop("ts"), timezone.utc).isoformat() if i.get("ts") else None
    return {"ticker": t, "headlines": items}


# ------------------------------------------------------------------ ideas (risk-checked)

def _ideas_this_week() -> int:
    text = repo_data.read_text(IDEAS_PATH)
    if not text:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    return sum(1 for r in csv.DictReader(io.StringIO(text)) if r["logged_at"] >= cutoff and r["side"] == "buy")


@safe
def check_trade_idea(ticker: str, side: str, position_pct: float = 0, stop: float = 0) -> dict:
    """Check an idea against the hard risk rules using live price and market cap."""
    t = _ticker(ticker)
    price = None
    closes = market_data.get_closes([t], period="5d")
    if t in closes and len(closes[t].dropna()):
        price = float(closes[t].dropna().iloc[-1])
    cap = market_data.get_market_cap(t)
    res = risk.check(side, float(position_pct), price, float(stop) if stop else None, cap, _ideas_this_week())
    return {"ticker": t, "side": side, "price": price, "market_cap": cap, "approved": res.approved,
            "violations": res.violations, "warnings": res.warnings, "rules": risk.rules_text()}


@safe
def log_trade_idea(ticker: str, side: str, position_pct: float, stop: float, target: float,
                   horizon_days: int, thesis: str, invalidation: str, sources: str,
                   model: str = "") -> dict:
    """Risk-check an idea and, if approved, record it in data/agent_ideas.csv so the
    scorecard can grade it later. Recording an idea is NOT placing an order."""
    chk = check_trade_idea(ticker, side, position_pct, stop)
    if chk.get("error") or not chk.get("approved"):
        return {"logged": False, **chk}
    if not sources.strip():
        return {"logged": False, "error": "an idea needs at least one source link"}
    row = {"logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ticker": chk["ticker"],
           "side": side.lower(), "position_pct": position_pct, "entry_price": chk["price"], "stop": stop,
           "target": target, "horizon_days": horizon_days, "thesis": thesis[:500],
           "invalidation": invalidation[:300], "sources": sources[:500], "model": model}
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=IDEA_FIELDS).writerow(row)
    ok = repo_data.append_line(IDEAS_PATH, buf.getvalue().strip(), ",".join(IDEA_FIELDS),
                               f"agent: log {side} idea {chk['ticker']}")
    return {"logged": ok, "idea": row, "warnings": chk["warnings"],
            "note": None if ok else "Approved but not saved: set GITHUB_TOKEN with contents:write to enable logging."}


@safe
def get_trade_ideas(days: int = 90) -> dict:
    """Previously logged agent ideas."""
    text = repo_data.read_text(IDEAS_PATH)
    if not text:
        return {"ideas": []}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
    return {"ideas": [r for r in csv.DictReader(io.StringIO(text)) if r["logged_at"] >= cutoff]}


@safe
def get_risk_rules() -> dict:
    return {"rules": risk.rules_text()}


ALL_TOOLS = [get_watchlist, get_latest_signals, get_signal_history, get_scorecard, get_price_summary,
             get_recent_filings, get_insider_activity, get_news, check_trade_idea, log_trade_idea,
             get_trade_ideas, get_risk_rules]
READ_ONLY = {f.__name__ for f in ALL_TOOLS} - {"log_trade_idea"}
