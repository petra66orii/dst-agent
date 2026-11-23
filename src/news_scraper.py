"""Headlines from Google News RSS (free, no key)."""
from __future__ import annotations

import calendar
import time
from urllib.parse import quote_plus

import feedparser


def get_stock_news(ticker: str, limit: int = 10) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote_plus(ticker + ' stock')}+when:2d&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"[news] {ticker}: {e}")
        return []
    items = []
    for e in feed.entries[:limit]:
        ts = calendar.timegm(e.published_parsed) if getattr(e, "published_parsed", None) else None
        items.append({"title": e.title, "link": e.get("link", ""), "ts": ts})
    return items


def count_recent(items: list[dict], hours: float) -> int:
    cutoff = time.time() - hours * 3600
    return sum(1 for i in items if i.get("ts") and i["ts"] >= cutoff)
