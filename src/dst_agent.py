"""Daily signal engine: combines trend, insider and news components into Buy/Hold/Sell."""
from __future__ import annotations

import json
from datetime import datetime

from src import edgar, llm, market_data
from src.news_scraper import get_stock_news
from src.settings import BENCHMARK, DATA_DIR, LOG_DIR

# Trend carries the most weight because it's the only component with a long, robust
# track record. The scorecard will tell us whether these weights deserve changing.
WEIGHTS = {"momentum": 0.5, "insider": 0.25, "news": 0.25}
BUY_AT, SELL_AT = 0.25, -0.25


def load_tickers() -> list[str]:
    with open(DATA_DIR / "stocks.json") as f:
        return [t.upper() for t in json.load(f)]


def get_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def classify(score: float) -> tuple[str, str]:
    if score >= 2 * BUY_AT:
        return "Buy", "High"
    if score >= BUY_AT:
        return "Buy", "Low"
    if score <= 2 * SELL_AT:
        return "Sell", "High"
    if score <= SELL_AT:
        return "Sell", "Low"
    return "Hold", "Neutral"


def combine(components: dict) -> float:
    return round(sum(WEIGHTS[k] * components.get(k, 0.0) for k in WEIGHTS), 3)


def analyze_tickers(tickers: list[str], closes=None) -> dict:
    if closes is None:
        closes = market_data.get_closes(tickers + [BENCHMARK], period="1y")
    bench = closes[BENCHMARK] if BENCHMARK in closes else None

    signals = []
    for ticker in tickers:
        try:
            feats = {}
            if bench is not None and ticker in closes:
                feats = market_data.price_features(closes[ticker], bench)

            news_items = get_stock_news(ticker, limit=8)
            # Only headlines from verified outlets/wire services can move the score.
            verified = [n["title"] for n in news_items if n.get("verified_source")]
            news = llm.analyse_headlines(ticker, verified)

            try:
                insiders = edgar.insider_activity(ticker)
            except Exception as e:
                print(f"[insider] {ticker}: {e}")
                insiders = {"ticker": ticker, "error": str(e)}

            components = {
                "momentum": market_data.score_momentum(feats),
                "insider": edgar.score_insiders(insiders),
                "news": news["sentiment_score"],
            }
            score = combine(components)
            signal, confidence = classify(score)
            signals.append({
                "ticker": ticker,
                "signal": signal,
                "confidence": confidence,
                "score": score,
                "components": components,
                "price": feats,
                "news": news,
                "headlines": news_items[:3],
                "insiders": insiders,
            })
        except Exception as e:
            print(f"[signal] {ticker}: {e}")

    signals.sort(key=lambda s: s["score"], reverse=True)
    return {
        "buy": [s["ticker"] for s in signals if s["signal"] == "Buy"],
        "sell": [s["ticker"] for s in signals if s["signal"] == "Sell"],
        "hold": [s["ticker"] for s in signals if s["signal"] == "Hold"],
        "signals": signals,
        "benchmark": BENCHMARK,
        "benchmark_close": float(bench.dropna().iloc[-1]) if bench is not None and len(bench.dropna()) else None,
    }


def save_log(report: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / f"dst_{report['date']}.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
