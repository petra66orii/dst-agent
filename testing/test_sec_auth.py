#!/usr/bin/env python3
"""
Test SEC API authentication and endpoints
"""
import requests
from config.config import SEC_API_KEY

def test_sec_api_auth():
    """Test SEC API authentication and available endpoints"""
    print("=== Testing SEC API Authentication ===")
    
    base_url = "https://api.sec-api.io"
    
    # Test different header formats
    header_formats = [
        {"Authorization": SEC_API_KEY},
        {"Authorization": f"Bearer {SEC_API_KEY}"},
        {"Authorization": f"Token {SEC_API_KEY}"},
        {"x-api-key": SEC_API_KEY}
    ]
    
    # Test different endpoints
    endpoints = [
        "/search",
        "/extractor", 
        "/filings/search",
        "/insider-trading",
        ""  # Base URL
    ]
    
    for i, headers in enumerate(header_formats):
        print(f"\n--- Testing Header Format {i+1}: {list(headers.keys())[0]} ---")
        
        for endpoint in endpoints:
            try:
                url = base_url + endpoint
                
                # Simple test query
                test_data = {
                    "query": {
                        "query_string": {
                            "query": "formType:\"4\" AND cik:0000320193"
                        }
                    },
                    "from": "0",
                    "size": "1"
                }
                
                response = requests.post(url, headers=headers, json=test_data, timeout=10)
                print(f"  {endpoint or '/'}: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"    ✅ SUCCESS! Working endpoint found")
                    return url, headers
                elif response.status_code != 404:
                    print(f"    Response: {response.text[:100]}...")
                    
            except Exception as e:
                print(f"  {endpoint or '/'}: Error - {e}")
    
    print("\n❌ No working endpoint/header combination found")
    return None, None

if __name__ == "__main__":
    working_url, working_headers = test_sec_api_auth()
    if working_url:
        print(f"\n🎯 Use this URL: {working_url}")
        print(f"🎯 Use these headers: {working_headers}")
