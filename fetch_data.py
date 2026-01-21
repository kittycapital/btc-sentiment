"""
Bitcoin Price Prediction - Data Fetcher
Fetches data from specific Polymarket event:
"What price will Bitcoin hit before 2027?"
"""

import json
import requests
from datetime import datetime
import re

# Configuration
DATA_FILE = 'data.json'
EVENT_SLUG = 'what-price-will-bitcoin-hit-before-2027'
POLYMARKET_API = f'https://gamma-api.polymarket.com/events?slug={EVENT_SLUG}'

# Expected price targets from Polymarket
VALID_UPSIDE = [100000, 110000, 120000, 130000, 140000, 150000, 160000, 170000, 180000, 190000, 200000]
VALID_DOWNSIDE = [25000, 35000, 45000, 55000, 65000, 75000]


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
        
        upside = []
        downside = []
        
        for market in event.get('markets', []):
            try:
                question = market.get('groupItemTitle', '') or market.get('question', '')
                outcomes = json.loads(market.get('outcomes', '[]'))
                prices = json.loads(market.get('outcomePrices', '[]'))
                
                # Find Yes probability
                yes_idx = next((i for i, o in enumerate(outcomes) if 'yes' in o.lower()), 0)
                probability = float(prices[yes_idx]) * 100 if yes_idx < len(prices) else 0
                
                # Check for upside targets (↑)
                if '↑' in question:
                    for valid_price in VALID_UPSIDE:
                        price_str = f"{valid_price:,}"
                        if price_str in question or str(valid_price) in question:
                            upside.append({
                                'price': valid_price,
                                'probability': round(probability, 1),
                                'type': 'up'
                            })
                            break
                
                # Check for downside targets (↓)
                elif '↓' in question:
                    for valid_price in VALID_DOWNSIDE:
                        price_str = f"{valid_price:,}"
                        if price_str in question or str(valid_price) in question:
                            downside.append({
                                'price': valid_price,
                                'probability': round(probability, 1),
                                'type': 'down'
                            })
                            break
                    
            except Exception as e:
                continue
        
        # Remove duplicates and sort
        upside = list({m['price']: m for m in upside}.values())
        downside = list({m['price']: m for m in downside}.values())
        
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
