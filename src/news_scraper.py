import feedparser

def get_stock_news(ticker, limit=3):
    try:
        feed_url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(feed_url)
        return [entry.title for entry in feed.entries[:limit]]
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []
