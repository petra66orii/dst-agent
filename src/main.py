import os, sys
# Ensure project root is on sys.path so 'config' and sibling packages resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dst_agent import load_tickers, analyze_tickers, save_log, get_today
from send_report import send_to_discord
from news_scraper import get_stock_news
from insider_scraper import get_insider_activity

def main():
    tickers = load_tickers()
    result = analyze_tickers(tickers)

    # Get top 3 tickers from buy/sell for news
    top_movers = result["buy"][:2] + result["sell"][:2]
    
    # Get news for top movers
    news_dict = {}
    for ticker in top_movers:
        news_dict[ticker] = get_stock_news(ticker)

    # Get insider activity for all top movers
    insider_activities = []
    for ticker in top_movers:
        insider_data = get_insider_activity(ticker)  # Get raw data
        if insider_data and insider_data.get("notable") and insider_data["notable"] != ["No notable trades"]:
            insider_activities.extend(insider_data["notable"])

    report = {
        "agent": "DST",
        "date": get_today(),
        **result,
        "news": news_dict,
        "insider_activity": insider_activities
    }

    save_log(report)
    send_to_discord(report)

if __name__ == "__main__":
    main()