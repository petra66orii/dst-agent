#!/usr/bin/env python3
"""
Test script to verify insider scraping functionality
"""
from insider_scraper import get_insider_activity

def test_insider_scraping():
    print("Testing insider scraping...")
    
    # Test with a popular stock
    test_tickers = ["AAPL", "TSLA", "MSFT"]
    
    for ticker in test_tickers:
        print(f"\n--- Testing {ticker} ---")
        try:
            data = get_insider_activity(ticker)
            print(f"Recent buys: {data['recent_buys']}")
            print(f"Recent sells: {data['recent_sells']}")
            print(f"Last activity: {data['last_activity']}")
            print(f"Notable trades: {len(data['notable'])}")
            
            # Show first few notable trades
            for i, trade in enumerate(data['notable'][:3]):
                print(f"  {i+1}. {trade}")
                
        except Exception as e:
            print(f"Error testing {ticker}: {e}")

if __name__ == "__main__":
    test_insider_scraping()
