#!/usr/bin/env python3
"""
Debug script to see what the SEC API is actually returning
"""
import requests
from config.config import SEC_API_KEY

SEC_BASE_URL = "https://api.sec-api.io"
HEADERS = {
    "Authorization": SEC_API_KEY,
    "User-Agent": "DST-Agent/1.0"
}

def debug_cik_lookup(ticker: str):
    """Debug what the CIK lookup API returns"""
    print(f"\n=== Debugging CIK lookup for {ticker} ===")
    
    try:
        url = f"{SEC_BASE_URL}/mapping/ticker/{ticker.upper()}"
        print(f"URL: {url}")
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Type: {type(data)}")
            print(f"Response Data: {data}")
            
            if isinstance(data, list):
                print(f"List Length: {len(data)}")
                if len(data) > 0:
                    print(f"First Item Type: {type(data[0])}")
                    print(f"First Item: {data[0]}")
            elif isinstance(data, dict):
                print(f"Dict Keys: {list(data.keys())}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test with a few tickers
    test_tickers = ["AAPL", "MSFT", "TSLA"]
    
    for ticker in test_tickers:
        debug_cik_lookup(ticker)
        
    print("\n=== Debug Complete ===")
