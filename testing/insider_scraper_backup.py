import json
import requests
from bs4 import BeautifulSoup
from typing import List
from datetime import datetime, timedelta
from openai import OpenAI
from config.config import OPENAI_API_KEY

HEADERS = {"User-Agent": "Mozilla/5.0"}
INSIDER_BASE = "https://www.quiverquant.com/sources/insidertrading/"
SENATE_BASE = "https://www.quiverquant.com/sources/senatetrading/"

# --- Helper to parse a QuiverQuant trading table (insider/senator) ---
def parse_quiver_table(url, days_back=30):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        rows = table.find_all("tr")[1:]  # Skip headers
        recent_trades = []
        cutoff = datetime.today() - timedelta(days=days_back)

        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 6:
                continue

            try:
                trade_date = datetime.strptime(cols[0], "%m/%d/%Y")
            except ValueError:
                continue

            if trade_date < cutoff:
                continue

            trade = {
                "date": trade_date,
                "name": cols[1],
                "title": cols[2],
                "type": cols[3].lower(),  # buy/sell
                "shares": cols[4],
                "source": "senator" if "senatetrading" in url else "insider"
            }
            recent_trades.append(trade)

        return recent_trades
    except Exception as e:
        print(f"Error parsing QuiverQuant table from {url}: {e}")
        return []

def get_insider_activity(ticker: str):
    ticker = ticker.upper()
    insider_url = INSIDER_BASE + ticker
    senate_url = SENATE_BASE + ticker

    all_trades = parse_quiver_table(insider_url) + parse_quiver_table(senate_url)

    buys = 0
    sells = 0
    latest = None
    notable = []

    for trade in all_trades:
        shares_str = trade.get("shares", "").replace(",", "")
        try:
            shares = int(shares_str)
        except:
            shares = 0

        if trade["type"] == "buy":
            buys += 1
            if shares > 1000:
                notable.append(f"[{trade['source']}] {trade['title']} {trade['name']} bought {shares:,} shares")
        elif trade["type"] == "sell":
            sells += 1
            if shares > 1000:
                notable.append(f"[{trade['source']}] {trade['title']} {trade['name']} sold {shares:,} shares")

        if not latest or trade["date"] > latest:
            latest = trade["date"]

    return {
        "ticker": ticker,
        "recent_buys": buys,
        "recent_sells": sells,
        "last_activity": latest.strftime("%Y-%m-%d") if latest else "N/A",
        "notable": notable or ["No notable trades"],
    }

def analyze_insider_activity_with_gpt(ticker: str, trades: List[str]) -> dict:
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
You are an insider trading analyst.

Summarize the recent insider trading activity for {ticker}.
Evaluate whether the overall sentiment is bullish or bearish and provide a sentiment score from -1 to 1.

Here are the recent insider trades:
{chr(10).join(f"- {t}" for t in trades)}

Return your response in this JSON format:
{{
  "summary": "...",
  "sentiment_score": 0.0
}}
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    content = response.choices[0].message.content
    return json.loads(content)
