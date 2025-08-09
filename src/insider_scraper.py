import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from config.config import SEC_API_KEY, OPENAI_API_KEY
import json
import time
from datetime import datetime
from openai import OpenAI

def get_company_cik(ticker):
    """Get CIK for a company ticker symbol"""
    # Hardcoded CIKs for common tickers (more reliable than API lookup)
    cik_mappings = {
        'AAPL': '320193',
        'MSFT': '789019',
        'TSLA': '1318605',
        'AMZN': '1018724',
        'GOOGL': '1652044',
        'META': '1326801',
        'NVDA': '1045810',
        'NFLX': '1065280',
        'AMD': '2488',
        'INTC': '50863',
        'GOOG': '1652044',  # Same as GOOGL
        'FB': '1326801',    # Same as META
        'JPM': '19617',
        'BAC': '70858',
        'WMT': '104169',
        'JNJ': '200406',
        'PG': '80424',
        'UNH': '731766',
        'HD': '354950',
        'V': '1403161',
        'ASTS': '1845524',
        'IBM': '51143',
        'SOUN': '1844791',
        'BSX': '885725'
    }
    
    return cik_mappings.get(ticker.upper())

def get_insider_transactions(ticker, limit=50):
    """Fetch insider trading data for a given ticker using SEC API"""
    
    if not SEC_API_KEY:
        print("SEC API key not found")
        return []
    
    # Use the correct SEC API endpoint for insider trading
    url = "https://api.sec-api.io/insider-trading"
    
    headers = {
        'Authorization': SEC_API_KEY,
        'Content-Type': 'application/json'
    }
    
    # Query payload according to SEC API documentation
    payload = {
        "query": f"issuer.tradingSymbol:{ticker.upper()}",
        "from": "0",
        "size": str(min(limit, 50)),  # API max is 50
        "sort": [{"filedAt": {"order": "desc"}}]
    }
    
    try:
        print(f"Fetching insider data for {ticker} from SEC API...")
        response = requests.post(url, headers=headers, json=payload)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Successfully retrieved {len(data.get('transactions', []))} transactions")
            return parse_insider_data(data.get("transactions", []))
        else:
            print(f"Error response: {response.text}")
            return []
            
    except Exception as e:
        print(f"Error fetching insider data for {ticker}: {e}")
        return []

def parse_insider_data(transactions):
    """Parse insider trading data into a standardized format"""
    parsed_data = []
    
    for transaction in transactions[:10]:  # Limit to 10 most recent
        try:
            # Extract basic transaction info
            insider_name = transaction.get('reportingOwner', {}).get('name', 'Unknown')
            relationship = transaction.get('reportingOwner', {}).get('relationship', {})
            
            # Determine relationship type
            relationship_type = []
            if relationship.get('isDirector'):
                relationship_type.append('Director')
            if relationship.get('isOfficer'):
                officer_title = relationship.get('officerTitle', 'Unknown')
                relationship_type.append(f"Officer ({officer_title})")
            if relationship.get('isTenPercentOwner'):
                relationship_type.append('10% Owner')
            if relationship.get('isOther'):
                other_text = relationship.get('otherText', 'Other')
                relationship_type.append(f"Other ({other_text})")
            
            # Create a more descriptive relationship string
            if not relationship_type:
                relationship_str = 'Company Insider'
            else:
                relationship_str = ', '.join(relationship_type)
            
            # Extract transaction details from non-derivative table
            non_derivative = transaction.get('nonDerivativeTable', {}).get('transactions', [])
            
            for txn in non_derivative:
                amounts = txn.get('amounts', {})
                shares = amounts.get('shares', 0)
                price = amounts.get('pricePerShare', 0)
                code = txn.get('coding', {}).get('code', 'Unknown')
                acquired_disposed = amounts.get('acquiredDisposedCode', 'Unknown')
                
                # Determine transaction type based on code and acquired/disposed
                if code == 'P':
                    txn_type = 'Purchase'
                elif code == 'S':
                    txn_type = 'Sale'
                elif code == 'A':
                    txn_type = 'Grant/Award'
                elif code == 'D':
                    txn_type = 'Disposition'
                elif code == 'F':
                    txn_type = 'Tax Payment'
                elif code == 'G':
                    txn_type = 'Gift'
                elif code == 'J':
                    txn_type = 'Other'
                else:
                    txn_type = f'Other ({code})'
                
                # Ensure shares and price are numeric
                try:
                    shares = float(shares) if shares else 0
                    price = float(price) if price else 0
                except (ValueError, TypeError):
                    shares = 0
                    price = 0
                
                parsed_data.append({
                    'insider_name': insider_name,
                    'relationship': relationship_str,
                    'transaction_date': txn.get('transactionDate', ''),
                    'transaction_type': txn_type,
                    'shares': shares,
                    'price_per_share': price,
                    'total_value': shares * price if shares and price else 0,
                    'filed_date': transaction.get('filedAt', '')[:10] if transaction.get('filedAt') else '',
                    'acquired_disposed': acquired_disposed
                })
                
        except Exception as e:
            print(f"Error parsing transaction: {e}")
            continue
    
    print(f"Parsed {len(parsed_data)} insider transactions")
    return parsed_data

def get_insider_activity(ticker):
    """Get insider trading activity for a given ticker"""
    insider_data = get_insider_transactions(ticker)
    
    if not insider_data:
        return {
            "ticker": ticker,
            "recent_buys": 0,
            "recent_sells": 0,
            "last_activity": "N/A",
            "notable": ["No insider data available"],
        }
    
    buys = 0
    sells = 0
    notable = []
    latest_date = None
    
    for trade in insider_data:
        try:
            # Count buys vs sells
            if trade['acquired_disposed'] == 'A' or trade['transaction_type'] in ['Purchase', 'Grant/Award']:
                buys += 1
            elif trade['acquired_disposed'] == 'D' or trade['transaction_type'] == 'Sale':
                sells += 1
            
            # Track notable trades (large volume or high value)
            if trade['shares'] > 1000 or trade['total_value'] > 50000:
                notable.append(f"{trade['insider_name']} ({trade['relationship']}) - {ticker} {trade['transaction_type']}: {trade['shares']:,.0f} shares @ ${trade['price_per_share']:.2f}")
            
            # Find latest activity date
            if trade['transaction_date']:
                if not latest_date or trade['transaction_date'] > latest_date:
                    latest_date = trade['transaction_date']
                    
        except Exception as e:
            print(f"Error processing insider trade: {e}")
            continue
    
    return {
        "ticker": ticker,
        "recent_buys": buys,
        "recent_sells": sells,
        "last_activity": latest_date or "N/A",
        "notable": notable[:5] if notable else ["No notable trades"],  # Limit to 5 most notable
    }

def analyze_insider_activity_with_gpt(ticker, trades):
    """Analyze insider trading activity using GPT"""
    if not OPENAI_API_KEY:
        return {
            "summary": f"Recent insider activity for {ticker}: {len(trades)} notable trades",
            "sentiment_score": 0.0
        }
    
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

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error analyzing insider activity with GPT: {e}")
        return {
            "summary": f"Recent insider activity for {ticker}: {len(trades)} notable trades",
            "sentiment_score": 0.0
        }
