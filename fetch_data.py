"""
Crypto Price Prediction - Multi-Asset, Multi-Timeframe Data Fetcher
Fetches prediction data from Polymarket for BTC, ETH, SOL
across yearly, monthly, and weekly timeframes.
"""

import json
import requests
from datetime import datetime, timedelta
import calendar
import re

# Configuration
DATA_FILE = 'data.json'
POLYMARKET_API = 'https://gamma-api.polymarket.com/events'

# ─── Asset Definitions ───────────────────────────────────────────────
ASSETS = {
    'btc': {
        'name': 'Bitcoin',
        'symbol': 'BTC',
        'slug_name': 'bitcoin',
        'coingecko_id': 'bitcoin',
        'fallback_price': 68000,
        'yearly_upside': [75000, 80000, 85000, 90000, 95000, 100000, 110000, 120000, 130000, 140000, 150000, 160000, 170000, 180000, 190000, 200000, 250000],
        'yearly_downside': [25000, 30000, 35000, 40000, 45000, 50000, 55000, 60000, 65000, 70000, 75000],
    },
    'eth': {
        'name': 'Ethereum',
        'symbol': 'ETH',
        'slug_name': 'ethereum',
        'coingecko_id': 'ethereum',
        'fallback_price': 2500,
        'yearly_upside': [3000, 3500, 4000, 4500, 5000, 5500, 6000, 7000, 8000, 9000, 10000],
        'yearly_downside': [800, 1000, 1200, 1400, 1500, 1600, 1800, 2000, 2200, 2500],
    },
    'sol': {
        'name': 'Solana',
        'symbol': 'SOL',
        'slug_name': 'solana',
        'coingecko_id': 'solana',
        'fallback_price': 85,
        'yearly_upside': [120, 140, 160, 180, 200, 220, 250, 300, 350, 400, 500],
        'yearly_downside': [30, 40, 50, 60, 70, 80, 90, 100],
    }
}


def fetch_current_prices():
    """Fetch current prices from CoinGecko for all assets"""
    try:
        ids = ','.join(a['coingecko_id'] for a in ASSETS.values())
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {'ids': ids, 'vs_currencies': 'usd'}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        prices = {}
        for key, asset in ASSETS.items():
            cg_id = asset['coingecko_id']
            prices[key] = data.get(cg_id, {}).get('usd', asset['fallback_price'])
        print(f"💰 Prices: " + ", ".join(f"{k.upper()}=${v:,.0f}" for k, v in prices.items()))
        return prices
    except Exception as e:
        print(f"⚠️ CoinGecko error: {e}, using fallbacks")
        return {k: v['fallback_price'] for k, v in ASSETS.items()}


# ─── Slug Builders ────────────────────────────────────────────────────

def get_yearly_slug(asset_key):
    """Static yearly slug"""
    name = ASSETS[asset_key]['slug_name']
    return f"what-price-will-{name}-hit-before-2027"


def get_monthly_slug(asset_key):
    """Build monthly slug from current date"""
    name = ASSETS[asset_key]['slug_name']
    now = datetime.utcnow()
    month_name = now.strftime('%B').lower()  # e.g., "february"
    year = now.year
    return f"what-price-will-{name}-hit-in-{month_name}-{year}"


def get_weekly_slug(asset_key):
    """
    Build weekly slug from current date.
    Polymarket weekly events run Monday-Sunday (7-day windows).
    Slug format: what-price-will-{name}-hit-{month}-{start_day}-{end_day}
    Cross-month weeks use abbreviated end day.
    
    Strategy: Try multiple slug patterns since exact date ranges vary.
    """
    name = ASSETS[asset_key]['slug_name']
    now = datetime.utcnow()
    
    # Generate candidate slugs for the current week
    # Find the Monday of this week
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    
    candidates = []
    
    # Primary: Monday-Sunday of current week
    candidates.append(build_weekly_slug_str(name, monday, sunday))
    
    # Also try with the actual Polymarket pattern (sometimes offset by a day)
    # Try Sunday-Saturday pattern too
    sat = monday + timedelta(days=5)
    candidates.append(build_weekly_slug_str(name, monday, sat))
    
    # Try Monday+1 to Sunday+1
    candidates.append(build_weekly_slug_str(name, monday - timedelta(days=1), sunday - timedelta(days=1)))
    candidates.append(build_weekly_slug_str(name, monday + timedelta(days=1), sunday + timedelta(days=1)))
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    
    return unique


def build_weekly_slug_str(name, start, end):
    """Build a single weekly slug string from start/end dates"""
    start_month = start.strftime('%B').lower()
    end_month = end.strftime('%B').lower()
    
    if start.month == end.month:
        # Same month: february-2-8
        return f"what-price-will-{name}-hit-{start_month}-{start.day}-{end.day}"
    else:
        # Cross-month: january-26-1 (abbreviated end day)
        return f"what-price-will-{name}-hit-{start_month}-{start.day}-{end.day}"


# ─── Polymarket API ───────────────────────────────────────────────────

def fetch_event(slug):
    """Fetch a single Polymarket event by slug"""
    try:
        response = requests.get(POLYMARKET_API, params={'slug': slug}, timeout=15)
        response.raise_for_status()
        events = response.json()
        if events and len(events) > 0:
            return events[0]
        return None
    except Exception as e:
        print(f"   ⚠️ API error for {slug}: {e}")
        return None


def parse_markets(event, asset_key):
    """
    Parse upside and downside markets from a Polymarket event.
    Works generically across all assets and timeframes.
    """
    if not event:
        return [], []
    
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
            
            # Extract price from question text
            price = extract_price(question, asset_key)
            if price is None:
                continue
            
            # Determine direction
            q_lower = question.lower()
            is_upside = any(indicator in q_lower for indicator in ['reach', '↑', 'hit'])
            is_downside = any(indicator in q_lower for indicator in ['dip', 'drop', 'fall', '↓'])
            
            # If neither indicator found, try to infer from context
            if not is_upside and not is_downside:
                # Check if it contains "reach" or "dip" in the broader question
                full_q = market.get('question', '').lower()
                is_upside = 'reach' in full_q
                is_downside = 'dip' in full_q or 'drop' in full_q
            
            if is_upside:
                upside.append({
                    'price': price,
                    'probability': round(probability, 1),
                    'type': 'up'
                })
            elif is_downside:
                downside.append({
                    'price': price,
                    'probability': round(probability, 1),
                    'type': 'down'
                })
                
        except Exception as e:
            continue
    
    # Remove duplicates, keep highest probability for each price
    upside = list({m['price']: m for m in sorted(upside, key=lambda x: x['probability'])}.values())
    downside = list({m['price']: m for m in sorted(downside, key=lambda x: x['probability'])}.values())
    
    upside.sort(key=lambda x: x['price'])
    downside.sort(key=lambda x: x['price'])
    
    return upside, downside


def extract_price(question, asset_key):
    """Extract the target price from a market question"""
    # Try patterns like $100,000 or $100K or $100k or plain numbers
    patterns = [
        r'\$?([\d,]+(?:\.\d+)?)\s*[kK]',      # $100K or 100k
        r'\$\s*([\d,]+(?:\.\d+)?)',              # $100,000 or $100.50
        r'([\d,]+(?:\.\d+)?)',                    # Plain number
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, question)
        for match in matches:
            try:
                num_str = match.replace(',', '')
                value = float(num_str)
                
                # Handle K suffix
                if 'k' in question.lower() and value < 10000:
                    # Check if this specific number had a K suffix
                    k_pattern = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*[kK]', question)
                    if k_pattern and k_pattern.group(1).replace(',', '') == num_str:
                        value *= 1000
                
                # Validate: price should be reasonable for the asset
                if is_valid_price(value, asset_key):
                    return value
            except:
                continue
    
    return None


def is_valid_price(price, asset_key):
    """Check if a price is reasonable for the given asset"""
    ranges = {
        'btc': (10000, 1000000),
        'eth': (200, 100000),
        'sol': (5, 10000),
    }
    lo, hi = ranges.get(asset_key, (0, float('inf')))
    return lo <= price <= hi


# ─── Expected Value Calculations ──────────────────────────────────────

def calculate_expected_high(upside_data, current_price):
    """Calculate expected high using marginal probabilities"""
    if not upside_data:
        return None
    
    sorted_data = sorted(upside_data, key=lambda x: x['price'])
    marginal_probs = []
    
    for i, item in enumerate(sorted_data):
        price = item['price']
        cumulative_prob = item['probability'] / 100
        
        if i + 1 < len(sorted_data):
            next_cumulative = sorted_data[i + 1]['probability'] / 100
        else:
            next_cumulative = 0
        
        marginal = max(0, cumulative_prob - next_cumulative)
        marginal_probs.append({'price': price, 'marginal': marginal})
    
    # Probability of not hitting the lowest upside target
    lowest_target = sorted_data[0]
    prob_below_lowest = 1 - (lowest_target['probability'] / 100)
    
    expected_high = current_price * prob_below_lowest
    for item in marginal_probs:
        expected_high += item['price'] * item['marginal']
    
    return round(expected_high, 0)


def calculate_expected_low(downside_data, current_price):
    """Calculate expected low using marginal probabilities"""
    if not downside_data:
        return None
    
    sorted_data = sorted(downside_data, key=lambda x: x['price'], reverse=True)
    marginal_probs = []
    
    for i, item in enumerate(sorted_data):
        price = item['price']
        cumulative_prob = item['probability'] / 100
        
        if i + 1 < len(sorted_data):
            next_cumulative = sorted_data[i + 1]['probability'] / 100
        else:
            next_cumulative = 0
        
        marginal = max(0, cumulative_prob - next_cumulative)
        marginal_probs.append({'price': price, 'marginal': marginal})
    
    highest_target = sorted_data[0]
    prob_above_highest = 1 - (highest_target['probability'] / 100)
    
    expected_low = current_price * prob_above_highest
    for item in marginal_probs:
        expected_low += item['price'] * item['marginal']
    
    return round(expected_low, 0)


# ─── Timeframe Fetchers ──────────────────────────────────────────────

def fetch_timeframe(asset_key, timeframe):
    """Fetch data for a specific asset + timeframe combination"""
    asset = ASSETS[asset_key]
    
    if timeframe == 'yearly':
        slug = get_yearly_slug(asset_key)
        slugs = [slug]
    elif timeframe == 'monthly':
        slug = get_monthly_slug(asset_key)
        slugs = [slug]
    elif timeframe == 'weekly':
        slugs = get_weekly_slug(asset_key)
    else:
        return None
    
    # Try each slug candidate
    event = None
    used_slug = None
    for slug in slugs:
        print(f"   Trying: {slug}")
        event = fetch_event(slug)
        if event:
            used_slug = slug
            break
    
    if not event:
        print(f"   ❌ No event found for {asset_key}/{timeframe}")
        return None
    
    print(f"   ✅ Found: {event.get('title', 'Unknown')} (slug: {used_slug})")
    
    upside, downside = parse_markets(event, asset_key)
    print(f"   📊 Upside: {len(upside)} targets, Downside: {len(downside)} targets")
    
    # Get period label
    now = datetime.utcnow()
    if timeframe == 'yearly':
        period = "2026"
    elif timeframe == 'monthly':
        period = now.strftime('%B %Y')
    elif timeframe == 'weekly':
        # Extract from event title or slug
        period = event.get('title', '').replace('What price will ', '').replace(' hit ', ' ').strip()
        if not period:
            period = used_slug.split('hit-')[-1] if used_slug else 'This Week'
    
    return {
        'upside': upside,
        'downside': downside,
        'period': period,
        'event_title': event.get('title'),
        'event_slug': used_slug,
        'end_date': event.get('endDate')
    }


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    print("🚀 Starting Multi-Asset Crypto Prediction fetch...\n")
    
    # Fetch current prices
    prices = fetch_current_prices()
    
    # Build output structure
    output = {
        'assets': {},
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }
    
    for asset_key in ASSETS:
        asset = ASSETS[asset_key]
        current_price = prices[asset_key]
        
        print(f"\n{'='*60}")
        print(f"📡 {asset['name']} ({asset['symbol']}) - ${current_price:,.2f}")
        print(f"{'='*60}")
        
        asset_data = {
            'name': asset['name'],
            'symbol': asset['symbol'],
            'current_price': current_price,
            'timeframes': {}
        }
        
        for timeframe in ['yearly', 'monthly', 'weekly']:
            print(f"\n⏱️  {timeframe.upper()}:")
            tf_data = fetch_timeframe(asset_key, timeframe)
            
            if tf_data:
                expected_high = calculate_expected_high(tf_data['upside'], current_price)
                expected_low = calculate_expected_low(tf_data['downside'], current_price)
                
                asset_data['timeframes'][timeframe] = {
                    'upside': tf_data['upside'],
                    'downside': tf_data['downside'],
                    'expected_high': expected_high,
                    'expected_low': expected_low,
                    'period': tf_data['period'],
                    'event_title': tf_data['event_title'],
                    'event_slug': tf_data['event_slug'],
                    'end_date': tf_data['end_date']
                }
                
                if expected_high:
                    print(f"   📈 Expected High: ${expected_high:,.0f}")
                if expected_low:
                    print(f"   📉 Expected Low: ${expected_low:,.0f}")
            else:
                asset_data['timeframes'][timeframe] = None
        
        output['assets'][asset_key] = asset_data
    
    # Save to JSON
    with open(DATA_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\n💾 Saved to {DATA_FILE}")
    print("✅ Done!")


if __name__ == '__main__':
    main()
