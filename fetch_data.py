"""
Bitcoin Price Prediction - Data Fetcher
Fetches data from specific Polymarket event:
"What price will Bitcoin hit before 2027?"
"""

import json
import requests
from datetime import datetime

# Configuration
DATA_FILE = 'data.json'
EVENT_SLUG = 'what-price-will-bitcoin-hit-before-2027'
POLYMARKET_API = f'https://gamma-api.polymarket.com/events?slug={EVENT_SLUG}'


def fetch_btc_current_price():
    """Fetch current BTC price from CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {'ids': 'bitcoin', 'vs_currencies': 'usd'}
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data['bitcoin']['usd']
    except:
        return 95000  # Fallback


def fetch_polymarket_data():
    """Fetch Bitcoin price predictions from specific Polymarket event"""
    
    print("📡 Fetching Polymarket Bitcoin predictions...")
    print(f"   Event: {EVENT_SLUG}")
    
    try:
        response = requests.get(POLYMARKET_API)
        response.raise_for_status()
        events = response.json()
        
        if not events:
            print("   ❌ Event not found")
            return None
        
        event = events[0]
        print(f"   ✅ Found: {event.get('title')}")
        
        upside = []  # ↑ targets (price going UP to this level)
        downside = []  # ↓ targets (price going DOWN to this level)
        
        for market in event.get('markets', []):
            try:
                question = market.get('groupItemTitle', '') or market.get('question', '')
                outcomes = json.loads(market.get('outcomes', '[]'))
                prices = json.loads(market.get('outcomePrices', '[]'))
                
                # Find Yes probability
                yes_idx = next((i for i, o in enumerate(outcomes) if 'yes' in o.lower()), 0)
                probability = float(prices[yes_idx]) * 100 if yes_idx < len(prices) else 0
                
                # Extract price target
                import re
                match = re.search(r'(\d{2,3}),?(\d{3})', question)
                if match:
                    price = int(match.group(1) + match.group(2))
                else:
                    match = re.search(r'(\d+)', question)
                    if match:
                        price = int(match.group(1))
                        if price < 1000:
                            price *= 1000
                    else:
                        continue
                
                # Determine if upside or downside based on arrow in question
                if '↑' in question:
                    upside.append({
                        'price': price,
                        'probability': round(probability, 1),
                        'type': 'up'
                    })
                elif '↓' in question:
                    downside.append({
                        'price': price,
                        'probability': round(probability, 1),
                        'type': 'down'
                    })
                    
            except Exception as e:
                continue
        
        # Sort by price
        upside.sort(key=lambda x: x['price'])
        downside.sort(key=lambda x: x['price'])
        
        print(f"   ✅ Upside targets: {len(upside)}")
        print(f"   ✅ Downside targets: {len(downside)}")
        
        return {
            'upside': upside,
            'downside': downside,
            'event_title': event.get('title'),
            'end_date': event.get('endDate')
        }
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def main():
    print("🚀 Starting Bitcoin Price Prediction fetch...\n")
    
    # Fetch predictions
    data = fetch_polymarket_data()
    
    if not data:
        print("❌ Failed to fetch data")
        return
    
    # Fetch current BTC price
    btc_price = fetch_btc_current_price()
    print(f"\n💰 Current BTC Price: ${btc_price:,.0f}")
    
    # Save to JSON
    output = {
        'upside': data['upside'],
        'downside': data['downside'],
        'current_price': btc_price,
        'event_title': data['event_title'],
        'end_date': data['end_date'],
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }
    
    with open(DATA_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Saved to {DATA_FILE}")
    
    # Print summary
    print("\n📈 Upside Predictions:")
    for m in data['upside']:
        print(f"   ${m['price']:,} → {m['probability']}%")
    
    print("\n📉 Downside Predictions:")
    for m in data['downside']:
        print(f"   ${m['price']:,} → {m['probability']}%")


if __name__ == '__main__':
    main()
