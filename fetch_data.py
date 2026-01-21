"""
Bitcoin Market Sentiment - Data Fetcher
Fetches Bitcoin prediction markets from Polymarket API
"""

import json
import requests
from datetime import datetime
import re

# Configuration
DATA_FILE = 'data.json'
POLYMARKET_API = 'https://gamma-api.polymarket.com/events'


def extract_price_target(text):
    """Extract price target from text like '$100K', '$150,000', '100000' etc."""
    
    # Pattern for $100K, $150k format
    match = re.search(r'\$?(\d+)[kK]', text)
    if match:
        return int(match.group(1)) * 1000
    
    # Pattern for $100,000 or $100000 format
    match = re.search(r'\$?([\d,]+)', text)
    if match:
        num_str = match.group(1).replace(',', '')
        if len(num_str) >= 5:  # At least 10000
            return int(num_str)
    
    return None


def is_expired(end_date_str):
    """Check if the market has expired"""
    if not end_date_str:
        return False
    
    try:
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        now = datetime.now(end_date.tzinfo)
        return end_date < now
    except:
        return False


def fetch_polymarket_btc_markets():
    """Fetch Bitcoin-related prediction markets from Polymarket"""
    
    print("📡 Fetching Polymarket Bitcoin markets...")
    
    params = {
        'tag_id': 21,  # Crypto tag
        'active': 'true',
        'closed': 'false',
        'limit': 100
    }
    
    try:
        response = requests.get(POLYMARKET_API, params=params)
        response.raise_for_status()
        events = response.json()
        
        print(f"   ✅ Got {len(events)} crypto events")
        
        # Filter for Bitcoin markets
        btc_markets = []
        
        for event in events:
            title = (event.get('title') or '').lower()
            
            # Only Bitcoin-related
            if 'bitcoin' not in title and 'btc' not in title:
                continue
            
            # Skip daily/hourly/short-term markets
            skip_keywords = ['today', 'hour', 'up or down', 'tomorrow', 'january 2', 
                           'december 2', 'december 3', 'january 3', 'weekly', 'daily']
            if any(skip in title for skip in skip_keywords):
                continue
            
            # Skip expired markets
            end_date = event.get('endDate', '')
            if is_expired(end_date):
                continue
            
            # Extract market data
            if event.get('markets'):
                for market in event['markets']:
                    try:
                        outcomes = json.loads(market.get('outcomes', '[]'))
                        prices = json.loads(market.get('outcomePrices', '[]'))
                        
                        # Get market question (contains specific price target)
                        market_question = market.get('question', '') or market.get('groupItemTitle', '')
                        
                        # Try to extract price target
                        price_target = extract_price_target(market_question)
                        
                        # If no price in market question, try outcomes
                        if not price_target:
                            for outcome in outcomes:
                                price_target = extract_price_target(outcome)
                                if price_target:
                                    break
                        
                        # Find "Yes" probability
                        yes_index = None
                        for i, outcome in enumerate(outcomes):
                            if outcome.lower() == 'yes' or 'yes' in outcome.lower():
                                yes_index = i
                                break
                        
                        if yes_index is not None and yes_index < len(prices):
                            prob = float(prices[yes_index]) * 100
                            volume = float(market.get('volume') or 0)
                            
                            # Create display question
                            if price_target:
                                display_question = f"Bitcoin ${price_target:,} 도달"
                            else:
                                display_question = market_question or event.get('title', '')
                            
                            btc_markets.append({
                                'question': display_question,
                                'price_target': price_target,
                                'probability': round(prob, 1),
                                'volume': volume,
                                'end_date': end_date
                            })
                    except Exception as e:
                        continue
        
        # Remove duplicates (same price target, keep highest volume)
        unique_markets = {}
        for m in btc_markets:
            key = m.get('price_target') or m['question']
            if key not in unique_markets or m['volume'] > unique_markets[key]['volume']:
                unique_markets[key] = m
        
        btc_markets = list(unique_markets.values())
        
        # Sort by price target (if available) then by volume
        btc_markets.sort(key=lambda x: (x.get('price_target') or 0, -x['volume']))
        
        print(f"   ✅ Found {len(btc_markets)} Bitcoin markets")
        
        return btc_markets
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []


def main():
    print("🚀 Starting Bitcoin Sentiment data fetch...\n")
    
    # Fetch markets
    markets = fetch_polymarket_btc_markets()
    
    if not markets:
        print("❌ No markets found")
        return
    
    # Save to JSON
    output = {
        'markets': markets,
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }
    
    with open(DATA_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved {len(markets)} markets to {DATA_FILE}")
    
    # Print summary
    print("\n📊 Markets:")
    for m in markets:
        print(f"   • {m['question']} → {m['probability']}%")


if __name__ == '__main__':
    main()
