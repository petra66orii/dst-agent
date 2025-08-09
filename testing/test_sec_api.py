#!/usr/bin/env python3
"""
Test script to verify SEC API insider scraping functionality
"""
from insider_scraper import get_insider_activity, get_company_cik

def test_sec_api():
    print("Testing SEC API insider scraping...")
    
    # Test CIK lookup first
    test_tickers = ["AAPL", "TSLA", "MSFT"]
    
    for ticker in test_tickers:
        print(f"\n--- Testing {ticker} ---")
        
        # Test CIK lookup
        cik = get_company_cik(ticker)
        if cik:
            print(f"✅ CIK found: {cik}")
        else:
            print(f"❌ Could not find CIK for {ticker}")
            continue
        
        # Test insider activity
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
            print(f"❌ Error testing {ticker}: {e}")
    
    print("\n=== SEC API Test Complete ===")

if __name__ == "__main__":
    test_sec_api()
