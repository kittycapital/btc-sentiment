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


def calculate_expected_high(upside_data, current_price):
    """
    Calculate expected high using marginal probabilities.
    
    Polymarket probabilities are cumulative:
    - P(hits $120k) = 70% means 70% chance BTC reaches $120k or higher
    - P(hits $130k) = 55% means 55% chance BTC reaches $130k or higher
    
    Marginal probability (chance this is the actual peak):
    - P(peak = $120k) = P(hits $120k) - P(hits $130k) = 70% - 55% = 15%
    
    Expected High = Σ (price × marginal_probability)
    """
    if not upside_data:
        return None
    
    # Sort by price ascending
    sorted_data = sorted(upside_data, key=lambda x: x['price'])
    
    marginal_probs = []
    total_marginal = 0
    
    for i, item in enumerate(sorted_data):
        price = item['price']
        cumulative_prob = item['probability'] / 100  # Convert to decimal
        
        # Next higher price's cumulative probability (0 if this is the highest)
        if i + 1 < len(sorted_data):
            next_cumulative = sorted_data[i + 1]['probability'] / 100
        else:
            next_cumulative = 0
        
        # Marginal probability = this cumulative - next cumulative
        marginal = cumulative_prob - next_cumulative
        marginal = max(0, marginal)  # Ensure non-negative
        
        marginal_probs.append({
            'price': price,
            'marginal': marginal
        })
        total_marginal += marginal
    
    # Also account for probability of NOT hitting the lowest upside target
    # This means the "peak" is somewhere below the lowest target (i.e., current price area)
    lowest_target = sorted_data[0]
    prob_below_lowest = 1 - (lowest_target['probability'] / 100)
    
    # Calculate expected value
    expected_high = 0
    
    # Contribution from price staying below lowest target (use current price as proxy)
    expected_high += current_price * prob_below_lowest
    
    # Contribution from each target being the peak
    for item in marginal_probs:
        expected_high += item['price'] * item['marginal']
    
    return round(expected_high, 0)


def calculate_expected_low(downside_data, current_price):
    """
    Calculate expected low using marginal probabilities.
    
    Polymarket downside probabilities are cumulative:
    - P(drops to $75k) = 80% means 80% chance BTC drops to $75k or lower
    - P(drops to $65k) = 60% means 60% chance BTC drops to $65k or lower
    
    Marginal probability (chance this is the actual bottom):
    - P(bottom = $75k) = P(drops to $75k) - P(drops to $65k) = 80% - 60% = 20%
    
    Expected Low = Σ (price × marginal_probability)
    """
    if not downside_data:
        return None
    
    # Sort by price descending (highest downside target first)
    sorted_data = sorted(downside_data, key=lambda x: x['price'], reverse=True)
    
    marginal_probs = []
    
    for i, item in enumerate(sorted_data):
        price = item['price']
        cumulative_prob = item['probability'] / 100  # Convert to decimal
        
        # Next lower price's cumulative probability (0 if this is the lowest)
        if i + 1 < len(sorted_data):
            next_cumulative = sorted_data[i + 1]['probability'] / 100
        else:
            next_cumulative = 0
        
        # Marginal probability = this cumulative - next cumulative
        marginal = cumulative_prob - next_cumulative
        marginal = max(0, marginal)  # Ensure non-negative
        
        marginal_probs.append({
            'price': price,
            'marginal': marginal
        })
    
    # Probability of NOT dropping to the highest downside target
    # This means BTC stays above all downside targets
    highest_target = sorted_data[0]
    prob_above_highest = 1 - (highest_target['probability'] / 100)
    
    # Calculate expected value
    expected_low = 0
    
    # Contribution from price staying above highest downside target (use current price as proxy)
    expected_low += current_price * prob_above_highest
    
    # Contribution from each target being the bottom
    for item in marginal_probs:
        expected_low += item['price'] * item['marginal']
    
    return round(expected_low, 0)


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
    
    # Calculate expected high and low
    expected_high = calculate_expected_high(data['upside'], btc_price)
    expected_low = calculate_expected_low(data['downside'], btc_price)
    
    print(f"\n📊 Expected Values (Marginal Probability Method):")
    print(f"   Expected High: ${expected_high:,.0f}" if expected_high else "   Expected High: N/A")
    print(f"   Expected Low:  ${expected_low:,.0f}" if expected_low else "   Expected Low: N/A")
    
    # Save to JSON
    output = {
        'upside': data['upside'],
        'downside': data['downside'],
        'current_price': btc_price,
        'expected_high': expected_high,
        'expected_low': expected_low,
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
