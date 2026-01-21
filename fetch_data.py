"""
Bitcoin Market Sentiment - Data Fetcher
Fetches Bitcoin prediction markets from Polymarket API
"""

import json
import requests
from datetime import datetime

# Configuration
DATA_FILE = 'data.json'
POLYMARKET_API = 'https://gamma-api.polymarket.com/events'


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
            
            # Skip daily/hourly markets
            if any(skip in title for skip in ['today', 'hour', 'up or down', 'tomorrow', 'december 2']):
                continue
            
            # Extract market data
            if event.get('markets'):
                for market in event['markets']:
                    try:
                        outcomes = json.loads(market.get('outcomes', '[]'))
                        prices = json.loads(market.get('outcomePrices', '[]'))
                        
                        # Find "Yes" probability
                        yes_index = None
                        for i, outcome in enumerate(outcomes):
                            if outcome.lower() == 'yes' or 'yes' in outcome.lower():
                                yes_index = i
                                break
                        
                        if yes_index is not None and yes_index < len(prices):
                            prob = float(prices[yes_index]) * 100
                            volume = float(market.get('volume') or 0)
                            
                            btc_markets.append({
                                'question': event.get('title', ''),
                                'probability': round(prob, 1),
                                'volume': volume,
                                'end_date': event.get('endDate', '')
                            })
                    except Exception as e:
                        continue
        
        # Sort by volume
        btc_markets.sort(key=lambda x: x['volume'], reverse=True)
        
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
    print("\n📊 Top markets:")
    for m in markets[:5]:
        print(f"   • {m['question'][:50]}... → {m['probability']}%")


if __name__ == '__main__':
    main()
