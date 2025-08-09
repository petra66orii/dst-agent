#!/usr/bin/env python3
"""
Simple test for CIK lookup
"""
from insider_scraper import get_company_cik

def test_cik_lookup():
    test_tickers = ["AAPL", "MSFT", "TSLA", "NVDA", "AMD"]
    
    print("=== Testing CIK Lookup ===")
    
    for ticker in test_tickers:
        print(f"\nTesting {ticker}:")
        cik = get_company_cik(ticker)
        if cik:
            print(f"  ✅ CIK: {cik}")
        else:
            print(f"  ❌ No CIK found")

if __name__ == "__main__":
    test_cik_lookup()
