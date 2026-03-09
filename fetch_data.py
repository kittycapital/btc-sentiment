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
        # Cross-month: february-23-march-1
        return f"what-price-will-{name}-hit-{start_month}-{start.day}-{end_month}-{end.day}"


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


def search_events(keyword, limit=20):
    """Search Polymarket events by keyword"""
    try:
        params = {
            'title': keyword,
            'closed': 'false',
            'limit': limit,
        }
        response = requests.get(POLYMARKET_API, params=params, timeout=15)
        response.raise_for_status()
        events = response.json()
        return events if events else []
    except Exception as e:
        print(f"   ⚠️ Search error for '{keyword}': {e}")
        return []


def find_event_by_search(asset_key, timeframe):
    """
    Find the right Polymarket event using keyword search + filtering.
    More robust than slug matching — survives slug format changes.
    """
    asset = ASSETS[asset_key]
    name = asset['slug_name']  # bitcoin, ethereum, solana
    now = datetime.utcnow()

    # Step 1: Search with broad keyword
    search_term = f"{name} price"
    print(f"   🔍 Searching: '{search_term}'")
    events = search_events(search_term)

    if not events:
        # Try alternative search terms
        for alt in [asset['name'], asset['symbol']]:
            print(f"   🔍 Retry: '{alt} price'")
            events = search_events(f"{alt} price")
            if events:
                break

    if not events:
        print(f"   ❌ No events found for {name}")
        return None

    # Step 2: Filter by timeframe
    matched = None
    title_lower_list = []

    for event in events:
        title = (event.get('title') or '').lower()
        title_lower_list.append(title)

        # Must contain the asset name
        if name not in title and asset['symbol'].lower() not in title:
            continue

        # Must be about price prediction
        if not any(kw in title for kw in ['price', 'hit', 'reach', 'dip', 'drop']):
            continue

        if timeframe == 'yearly':
            # Look for year-based events (2026, 2027, etc.)
            if any(f"{y}" in title for y in [now.year, now.year + 1]):
                if 'before' in title or 'by' in title or 'end of' in title or str(now.year + 1) in title:
                    if matched is None:
                        matched = event
                        print(f"   ✅ Yearly match: {event.get('title')}")

        elif timeframe == 'monthly':
            # Look for current month name
            month_name = now.strftime('%B').lower()
            year_str = str(now.year)
            if month_name in title and year_str in title:
                if matched is None:
                    matched = event
                    print(f"   ✅ Monthly match: {event.get('title')}")

        elif timeframe == 'weekly':
            # Look for weekly events — check if event end date falls within this week
            end_date_str = event.get('endDate', '')
            if end_date_str:
                try:
                    # Parse end date (ISO format)
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    monday = now - timedelta(days=now.weekday())
                    sunday = monday + timedelta(days=6)
                    # Event ends within this week or next 2 days
                    if monday <= end_date <= sunday + timedelta(days=2):
                        if matched is None:
                            matched = event
                            print(f"   ✅ Weekly match: {event.get('title')}")
                except Exception:
                    pass

            # Also try matching day numbers in title
            if matched is None:
                monday = now - timedelta(days=now.weekday())
                sunday = monday + timedelta(days=6)
                month_name = now.strftime('%B').lower()
                # Check if title contains date range like "march 3-9"
                if month_name in title and any(str(d) in title for d in range(monday.day, sunday.day + 1)):
                    matched = event
                    print(f"   ✅ Weekly match (date): {event.get('title')}")

    if not matched:
        print(f"   ❌ No {timeframe} event matched from {len(events)} results")
        if title_lower_list:
            print(f"   📋 Available: {title_lower_list[:5]}")

    return matched


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
    
    # Primary: keyword search (robust)
    event = find_event_by_search(asset_key, timeframe)
    
    # Fallback: try slug-based approach
    if not event:
        print(f"   🔄 Falling back to slug-based search...")
        if timeframe == 'yearly':
            slugs = [get_yearly_slug(asset_key)]
        elif timeframe == 'monthly':
            slugs = [get_monthly_slug(asset_key)]
        elif timeframe == 'weekly':
            slugs = get_weekly_slug(asset_key)
        else:
            slugs = []
        
        for slug in slugs:
            print(f"   Trying slug: {slug}")
            event = fetch_event(slug)
            if event:
                break
    
    if not event:
        print(f"   ❌ No event found for {asset_key}/{timeframe}")
        return None
    
    print(f"   ✅ Using: {event.get('title', 'Unknown')}")
    
    upside, downside = parse_markets(event, asset_key)
    print(f"   📊 Upside: {len(upside)} targets, Downside: {len(downside)} targets")
    
    # Get period label
    now = datetime.utcnow()
    if timeframe == 'yearly':
        period = str(now.year)
    elif timeframe == 'monthly':
        period = now.strftime('%B %Y')
    elif timeframe == 'weekly':
        period = event.get('title', '').replace('What price will ', '').replace(' hit ', ' ').strip()
        if not period:
            period = 'This Week'
    
    return {
        'upside': upside,
        'downside': downside,
        'period': period,
        'event_title': event.get('title'),
        'event_slug': event.get('slug'),
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
