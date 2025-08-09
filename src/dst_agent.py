import json
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime
from pathlib import Path
import requests
from typing import List
from openai import OpenAI
from news_scraper import get_stock_news
from insider_scraper import get_insider_activity, analyze_insider_activity_with_gpt
from config.config import ALPHA_VANTAGE_KEY, OPENAI_API_KEY

def get_fundamentals(ticker):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "OVERVIEW",
        "symbol": ticker,
        "apikey": ALPHA_VANTAGE_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "Symbol" in data:
            return {
                "PE": data.get("PERatio"),
                "EPS": data.get("EPS"),
                "MarketCap": data.get("MarketCapitalization"),
                "Sector": data.get("Sector"),
                "ROE": data.get("ReturnOnEquityTTM"),
            }
    except Exception as e:
        print(f"[ERROR] Fundamentals for {ticker}: {e}")
    return {}

def get_price_change_pct(ticker):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "apikey": ALPHA_VANTAGE_KEY,
        "outputsize": "compact"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json().get("Time Series (Daily)", {})
        if len(data) < 2:
            return None
        dates = sorted(data.keys(), reverse=True)
        last_close = float(data[dates[0]]["4. close"])
        prev_close = float(data[dates[1]]["4. close"])
        return ((last_close - prev_close) / prev_close) * 100
    except Exception as e:
        print(f"[ERROR] Price data for {ticker}: {e}")
    return None

WEIGHTS = {
    "price": 0.4,
    "news": 0.3,
    "insider": 0.3
}

def score_price_change(pct):
    if pct is None: return 0
    if pct > 5: return 1.0
    if pct > 2: return 0.7
    if pct > 0: return 0.3
    if pct > -2: return -0.3
    if pct > -5: return -0.7
    return -1.0

def analyze_news_with_gpt(ticker: str, headlines: List[str], fundamentals: dict) -> dict:
    if not OPENAI_API_KEY:
        return {
            "summary": "No OpenAI key provided; skipping AI news analysis.",
            "sentiment_score": 0.0,
            "reasoning": ""
        }

    client = OpenAI(api_key=OPENAI_API_KEY)

    fundamentals_str = "\n".join(f"- {k}: {v}" for k, v in fundamentals.items() if v)

    prompt = f"""
You are a financial analyst AI helping assess the investment outlook of stocks based on recent news and company fundamentals.

Stock: {ticker}

Fundamentals:
{fundamentals_str or 'N/A'}

Recent News Headlines:
{chr(10).join(f"- {h}" for h in headlines) or 'No recent headlines'}

Step 1: Briefly summarize the headlines in 2–3 sentences.
Step 2: Based on both news and fundamentals, give a sentiment score from -1 (bearish) to 1 (bullish), with justification.

Respond in JSON:
{{
  "summary": "...",
  "sentiment_score": 0.0,
  "reasoning": "..."
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"[ERROR] GPT news analysis for {ticker}: {e}")
        return {
            "summary": "AI analysis failed; using neutral score.",
            "sentiment_score": 0.0,
            "reasoning": ""
        }


def score_insider_activity(ticker, data):
    if not data: return 0
    buys = data.get("recent_buys", 0)
    sells = data.get("recent_sells", 0)
    return max(min((buys - sells) / 10, 1), -1)

def load_tickers():
    with open("data/stocks.json") as f:
        return json.load(f)

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def analyze_tickers(tickers):
    buy, sell, hold, signals = [], [], [], []

    for ticker in tickers:
        try:
            # Get fundamentals once and reuse
            fundamentals = get_fundamentals(ticker)
            
            pct_change = get_price_change_pct(ticker)
            price_score = score_price_change(pct_change)

            news = get_stock_news(ticker, limit=3)
            news_analysis = analyze_news_with_gpt(ticker, news, fundamentals)
            news_score = news_analysis.get("sentiment_score", 0)

            # Get raw insider data first
            insider_data = get_insider_activity(ticker)
            
            # Get insider analysis from GPT if there are notable trades
            if insider_data and insider_data.get("notable") and insider_data["notable"] != ["No notable trades"]:
                insider_analysis = analyze_insider_activity_with_gpt(ticker, insider_data["notable"])
            else:
                insider_analysis = {"summary": "No significant insider activity", "sentiment_score": 0}
            
            insider_score = score_insider_activity(ticker, insider_data)

            final_score = (
                WEIGHTS["price"] * price_score +
                WEIGHTS["news"] * news_score +
                WEIGHTS["insider"] * insider_score
            )

            if final_score >= 0.5:
                buy.append(ticker)
                signal = "Buy"
                confidence = "High"
            elif final_score >= 0.2:
                buy.append(ticker)
                signal = "Buy"
                confidence = "Low"
            elif final_score <= -0.5:
                sell.append(ticker)
                signal = "Sell"
                confidence = "High"
            elif final_score <= -0.2:
                sell.append(ticker)
                signal = "Sell"
                confidence = "Low"
            else:
                hold.append(ticker)
                signal = "Hold"
                confidence = "Neutral"

            signals.append({
                "ticker": ticker,
                "signal": signal,
                "confidence": confidence,
                "score": round(final_score, 3),
                "price_change_pct": round(pct_change, 2) if pct_change is not None else None,
                "news_analysis": news_analysis,
                "insider_data": insider_data,
                "insider_analysis": insider_analysis,
                "fundamentals": fundamentals
            })

        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            continue

    return {
        "buy": buy,
        "sell": sell,
        "hold": hold,
        "signals": signals
    }

def save_log(report):
    Path("logs").mkdir(exist_ok=True)
    with open(f"logs/dst_{get_today()}.json", "w") as f:
        json.dump(report, f, indent=2)
