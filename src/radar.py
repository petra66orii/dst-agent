"""Intraday event radar for the watchlist: new 8-K filings, big price moves, news spikes.

    python -m src.radar

Designed to run every hour during US market hours. Remembers what it already alerted on
(data/radar_state.json) so each event is only posted once.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from src import edgar, market_data
from src.dst_agent import load_tickers
from src.news_scraper import count_recent, get_stock_news
from src.send_report import post
from src.settings import DATA_DIR, DISCORD_ALERTS_WEBHOOK_URL, RADAR_MOVE_PCT, RADAR_NEWS_SPIKE

STATE_FILE = DATA_DIR / "radar_state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"seen_filings": [], "alerted": []}


def save_state(state: dict) -> None:
    # keep the files small: the last 500 of each is plenty
    state = {k: v[-500:] for k, v in state.items()}
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1))


def check_filings(ticker: str, cik: int, state: dict, since: date) -> list[str]:
    alerts = []
    for f in edgar.recent_filings(cik, {"8-K", "8-K/A"}, since):
        if f["accession"] in state["seen_filings"]:
            continue
        state["seen_filings"].append(f["accession"])
        labels = [f"{i} {edgar.EIGHT_K_ITEMS.get(i, '')}".strip() for i in f["items"] if i != "9.01"]
        high = any(i in edgar.HIGH_IMPACT_ITEMS for i in f["items"])
        icon = "🚨" if high else "📄"
        alerts.append(f"{icon} **{ticker}** filed {f['form']} ({f['filed']}): {', '.join(labels) or 'see filing'}\n"
                      f"<{edgar.filing_url(cik, f['accession'], f['primary_doc'])}>")
    return alerts


def move_bucket(pct: float, threshold: float) -> int:
    """0 if below threshold, else 1, 2, 3... for each multiple of the threshold."""
    return int(abs(pct) // threshold)


def check_move(ticker: str, state: dict, today: str) -> list[str]:
    bars = market_data.get_intraday(ticker)
    if bars is None or bars.empty:
        return []
    days = sorted({ts.date() for ts in bars.index})
    if len(days) < 2 or days[-1].isoformat() != today:
        return []  # market not open yet today (avoid re-reporting yesterday's move)
    prev_close = float(bars[[ts.date() == days[-2] for ts in bars.index]]["Close"].iloc[-1])
    last = float(bars["Close"].iloc[-1])
    pct = (last / prev_close - 1) * 100
    bucket = move_bucket(pct, RADAR_MOVE_PCT)
    key = f"move:{ticker}:{today}:{'up' if pct > 0 else 'down'}:{bucket}"
    if bucket == 0 or key in state["alerted"]:
        return []
    state["alerted"].append(key)
    icon = "📈" if pct > 0 else "📉"
    return [f"{icon} **{ticker}** {pct:+.1f}% vs previous close (${last:.2f})"]


def check_news(ticker: str, state: dict, today: str) -> list[str]:
    items = get_stock_news(ticker, limit=30)
    n = count_recent(items, hours=3)
    key = f"news:{ticker}:{today}"
    if n < RADAR_NEWS_SPIKE or key in state["alerted"]:
        return []
    state["alerted"].append(key)
    top = "\n".join(f"  – {i['title']}" for i in items[:3])
    return [f"📰 **{ticker}** news spike: {n} headlines in 3h\n{top}"]


def run() -> list[str]:
    state = load_state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    since = date.today() - timedelta(days=2)
    alerts = []
    for ticker in load_tickers():
        for check in (
            lambda: check_filings(ticker, edgar.get_cik(ticker), state, since),
            lambda: check_move(ticker, state, today),
            lambda: check_news(ticker, state, today),
        ):
            try:
                alerts.extend(check())
            except Exception as e:
                print(f"[radar] {ticker}: {e}")
    save_state(state)
    if alerts:
        post("⚡ **DST Radar**\n" + "\n".join(alerts), webhook=DISCORD_ALERTS_WEBHOOK_URL)
    print(f"{len(alerts)} alert(s)")
    return alerts


if __name__ == "__main__":
    run()
