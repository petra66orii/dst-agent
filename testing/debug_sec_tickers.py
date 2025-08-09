#!/usr/bin/env python3
"""
Test script to see what's in the SEC company tickers file
"""
import requests
import json

def debug_sec_tickers():
    """Debug what the SEC company tickers file contains"""
    print("=== Debugging SEC Company Tickers ===")
    
    try:
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(tickers_url, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Data type: {type(data)}")
            print(f"Number of entries: {len(data)}")
            
            # Show first few entries to understand structure
            print("\nFirst 5 entries:")
            for i, (key, value) in enumerate(list(data.items())[:5]):
                print(f"  {key}: {value}")
            
            # Look for specific tickers
            test_tickers = ["AAPL", "MSFT", "TSLA"]
            print(f"\nSearching for test tickers: {test_tickers}")
            
            for company_key, company_info in data.items():
                if isinstance(company_info, dict):
                    ticker = company_info.get("ticker", "").upper()
                    if ticker in test_tickers:
                        print(f"Found {ticker}: {company_info}")
                        
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_sec_tickers()
