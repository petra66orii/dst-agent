import json
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from openai import OpenAI
from config.config import OPENAI_API_KEY, SEC_API_KEY

# SEC API Configuration
SEC_BASE_URL = "https://api.sec-api.io"
HEADERS = {
    "Authorization": SEC_API_KEY,
    "User-Agent": "DST-Agent/1.0"
}

def get_company_cik(ticker: str) -> Optional[str]:
    """Get CIK (Central Index Key) for a given ticker symbol"""
    try:
        url = f"{SEC_BASE_URL}/mapping/ticker/{ticker.upper()}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("cik")
        else:
            print(f"Failed to get CIK for {ticker}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error getting CIK for {ticker}: {e}")
        return None

def get_insider_transactions(cik: str, days_back: int = 30) -> List[Dict]:
    """Get insider transactions for a company using SEC API"""
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # SEC API query for Form 4 filings (insider transactions)
        query = {
            "query": {
                "query_string": {
                    "query": f"formType:\"4\" AND cik:{cik} AND filedAt:[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
                }
            },
            "from": "0",
            "size": "50",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        
        url = f"{SEC_BASE_URL}/extractor"
        response = requests.post(url, headers=HEADERS, json=query, timeout=30)
        
        if response.status_code == 200:
            return response.json().get("filings", [])
        else:
            print(f"Failed to get insider transactions: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error getting insider transactions: {e}")
        return []

def parse_form4_data(filing: Dict) -> List[Dict]:
    """Parse Form 4 filing data to extract transaction details"""
    transactions = []
    
    try:
        # Extract basic filing info
        filed_date = filing.get("filedAt", "")
        reporter_name = ""
        reporter_title = ""
        
        # Parse the HTML content for transaction details
        # Note: This is a simplified parser - real Form 4s are complex
        if "reportingOwner" in filing:
            owner = filing["reportingOwner"]
            reporter_name = owner.get("reportingOwnerId", {}).get("rptOwnerName", "Unknown")
            reporter_title = owner.get("reportingOwnerRelationship", {}).get("officerTitle", "Insider")
        
        # Parse non-derivative transactions
        non_derivative_table = filing.get("nonDerivativeTable", {})
        if "nonDerivativeHolding" in non_derivative_table:
            holdings = non_derivative_table["nonDerivativeHolding"]
            if not isinstance(holdings, list):
                holdings = [holdings]
                
            for holding in holdings:
                transaction = {
                    "date": filed_date,
                    "name": reporter_name,
                    "title": reporter_title,
                    "type": holding.get("transactionAmounts", {}).get("transactionAcquiredDisposedCode", {}).get("value", "").lower(),
                    "shares": holding.get("transactionAmounts", {}).get("transactionShares", {}).get("value", "0"),
                    "source": "insider"
                }
                transactions.append(transaction)
    
    except Exception as e:
        print(f"Error parsing Form 4 data: {e}")
    
    return transactions

def get_insider_activity(ticker: str) -> Dict:
    """Get insider trading activity for a given ticker using SEC API"""
    ticker = ticker.upper()
    
    # Get company CIK
    cik = get_company_cik(ticker)
    if not cik:
        return {
            "ticker": ticker,
            "recent_buys": 0,
            "recent_sells": 0,
            "last_activity": "N/A",
            "notable": ["No data available - could not retrieve company CIK"],
        }
    
    # Get insider transactions
    filings = get_insider_transactions(cik)
    
    buys = 0
    sells = 0
    latest = None
    notable = []
    
    for filing in filings:
        transactions = parse_form4_data(filing)
        
        for transaction in transactions:
            try:
                # Parse transaction date
                transaction_date = datetime.strptime(transaction["date"][:10], "%Y-%m-%d")
                
                # Parse shares
                shares_str = str(transaction.get("shares", "0")).replace(",", "")
                try:
                    shares = float(shares_str)
                except:
                    shares = 0
                
                # Categorize transaction
                transaction_type = transaction.get("type", "").lower()
                if transaction_type in ["a", "acquired", "buy", "purchase"]:
                    buys += 1
                    if shares > 1000:
                        notable.append(f"[insider] {transaction['title']} {transaction['name']} bought {shares:,.0f} shares")
                elif transaction_type in ["d", "disposed", "sell", "sale"]:
                    sells += 1
                    if shares > 1000:
                        notable.append(f"[insider] {transaction['title']} {transaction['name']} sold {shares:,.0f} shares")
                
                # Track latest activity
                if not latest or transaction_date > latest:
                    latest = transaction_date
                    
            except Exception as e:
                print(f"Error processing transaction: {e}")
                continue
    
    return {
        "ticker": ticker,
        "recent_buys": buys,
        "recent_sells": sells,
        "last_activity": latest.strftime("%Y-%m-%d") if latest else "N/A",
        "notable": notable or ["No notable trades"],
    }

def analyze_insider_activity_with_gpt(ticker: str, trades: List[str]) -> Dict:
    """Analyze insider trading activity using GPT"""
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
