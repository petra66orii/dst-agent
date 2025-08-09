#!/usr/bin/env python3
"""
Test script to verify DST agent functionality
"""
from dst_agent import load_tickers, analyze_tickers, get_today
from news_scraper import get_stock_news
from insider_scraper import get_insider_activity

def test_basic_functionality():
    print("Testing DST Agent...")
    
    # Test ticker loading
    print("1. Testing ticker loading...")
    tickers = load_tickers()
    print(f"   Loaded {len(tickers)} tickers: {tickers[:5]}...")
    
    # Test with a small subset for faster testing
    test_tickers = tickers[:3]
    print(f"2. Testing analysis with {test_tickers}...")
    
    try:
        result = analyze_tickers(test_tickers)
        print(f"   Analysis complete:")
        print(f"   - Buy: {result['buy']}")
        print(f"   - Sell: {result['sell']}")
        print(f"   - Hold: {result['hold']}")
        print(f"   - Signals: {len(result['signals'])}")
    except Exception as e:
        print(f"   Error in analysis: {e}")
    
    # Test news scraping
    print("3. Testing news scraping...")
    try:
        news = get_stock_news("AAPL", limit=2)
        print(f"   Got {len(news)} news items for AAPL")
    except Exception as e:
        print(f"   Error in news scraping: {e}")
    
    # Test insider activity
    print("4. Testing insider activity...")
    try:
        insider = get_insider_activity("AAPL")
        print(f"   Insider data keys: {list(insider.keys())}")
    except Exception as e:
        print(f"   Error in insider activity: {e}")
    
    print("Test complete!")

if __name__ == "__main__":
    test_basic_functionality()
