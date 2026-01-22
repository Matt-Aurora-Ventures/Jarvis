"""
Bags Intel API Server
Serves real-time bags.fm graduation data to the webapp
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

try:
    from bots.bags_intel.models import GraduationEvent
except ImportError:
    print("Warning: Could not import bags_intel models")
    GraduationEvent = None


app = Flask(__name__, static_folder='.')
CORS(app)

# In-memory storage for graduation events
# In production, this would be a database
graduation_events: List[Dict[str, Any]] = []
MAX_EVENTS = 100  # Keep last 100 events

# Path to store events persistently
EVENTS_FILE = project_root / "webapp" / "bags-intel" / "events.json"


def load_events():
    """Load events from persistent storage"""
    global graduation_events

    if EVENTS_FILE.exists():
        try:
            with open(EVENTS_FILE, 'r') as f:
                graduation_events = json.load(f)
            print(f"Loaded {len(graduation_events)} events from storage")
        except Exception as e:
            print(f"Error loading events: {e}")
            graduation_events = []
    else:
        # Generate mock data for testing
        graduation_events = generate_mock_events()
        save_events()


def save_events():
    """Save events to persistent storage"""
    try:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENTS_FILE, 'w') as f:
            json.dump(graduation_events, f, indent=2)
    except Exception as e:
        print(f"Error saving events: {e}")


def generate_mock_events() -> List[Dict[str, Any]]:
    """Generate mock graduation events for testing"""
    import random

    qualities = ['exceptional', 'strong', 'average', 'weak', 'poor']
    risks = ['low', 'medium', 'high', 'extreme']

    token_names = [
        ('DOGE2.0', 'DogeRevolution', 'The meme lives on'),
        ('MOONCAT', 'Moon Cat Protocol', 'Cats to the moon'),
        ('SAFEAI', 'SafeAI Token', 'AI-powered safety'),
        ('WOJAK', 'Wojak Finance', 'For the culture'),
        ('GIGACHAD', 'GigaChad DAO', 'Maximum strength'),
        ('PEPE3', 'Pepe Returns', 'The comeback'),
        ('BASED', 'Based Protocol', 'Based and coded'),
        ('FREN', 'Frens United', 'Together strong'),
        ('DIAMOND', 'Diamond Hands', 'Never selling'),
        ('ROCKET', 'Rocket Finance', 'To infinity')
    ]

    events = []

    for i in range(20):
        symbol, name, description = random.choice(token_names)
        quality = qualities[min(i // 4, 4)]  # Distribute across qualities
        risk = risks[random.randint(0, 3)]

        # Generate plausible scores
        if quality == 'exceptional':
            overall = random.randint(85, 98)
            bonding = random.randint(85, 100)
            creator = random.randint(80, 95)
            social = random.randint(75, 90)
            market = random.randint(85, 100)
        elif quality == 'strong':
            overall = random.randint(70, 84)
            bonding = random.randint(70, 85)
            creator = random.randint(65, 80)
            social = random.randint(60, 75)
            market = random.randint(70, 85)
        elif quality == 'average':
            overall = random.randint(55, 69)
            bonding = random.randint(55, 70)
            creator = random.randint(50, 65)
            social = random.randint(45, 60)
            market = random.randint(55, 70)
        elif quality == 'weak':
            overall = random.randint(40, 54)
            bonding = random.randint(40, 55)
            creator = random.randint(35, 50)
            social = random.randint(30, 45)
            market = random.randint(40, 55)
        else:  # poor
            overall = random.randint(20, 39)
            bonding = random.randint(20, 40)
            creator = random.randint(15, 35)
            social = random.randint(10, 30)
            market = random.randint(20, 40)

        # Generate green flags
        green_flags = []
        if bonding > 75:
            green_flags.append("Strong bonding curve metrics")
        if creator > 70:
            green_flags.append("Verified creator with history")
        if social > 65:
            green_flags.append("Active social presence")
        if market > 75:
            green_flags.append("Healthy initial liquidity")

        # Generate red flags
        red_flags = []
        if bonding < 50:
            red_flags.append("Weak bonding performance")
        if creator < 40:
            red_flags.append("Anonymous or suspicious creator")
        if social < 35:
            red_flags.append("Limited social presence")
        if market < 50:
            red_flags.append("Low liquidity concerns")

        # Timestamp (recent to old)
        timestamp = datetime.utcnow() - timedelta(hours=i * 2)

        event = {
            "type": "bags_intel_report",
            "timestamp": timestamp.isoformat(),
            "token": {
                "mint": f"{''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=44))}",
                "name": name,
                "symbol": symbol,
                "description": description,
                "twitter": f"@{symbol.lower()}",
                "website": f"https://{symbol.lower()}.io",
            },
            "scores": {
                "overall": overall,
                "quality": quality,
                "risk": risk,
                "bonding": bonding,
                "creator": creator,
                "social": social,
                "market": market,
                "distribution": random.randint(50, 80)
            },
            "market": {
                "mcap_usd": random.randint(15000, 500000),
                "liquidity_usd": random.randint(5000, 100000),
                "price_usd": random.uniform(0.00001, 0.01),
                "volume_24h_usd": random.randint(10000, 250000)
            },
            "bonding_curve": {
                "duration_seconds": random.randint(600, 7200),
                "volume_sol": random.uniform(50, 500),
                "unique_buyers": random.randint(50, 500),
                "buy_sell_ratio": random.uniform(1.2, 5.0)
            },
            "creator": {
                "wallet": f"{''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=44))}",
                "twitter": f"@creator_{random.randint(1, 1000)}" if random.random() > 0.3 else None,
            },
            "flags": {
                "green": green_flags,
                "red": red_flags,
                "warnings": []
            },
            "ai_analysis": {
                "summary": f"{name} shows {quality} fundamentals with {risk} risk level. "
                           f"The bonding curve completed in {random.randint(10, 120)} minutes with "
                           f"{random.randint(50, 500)} unique participants. "
                           f"{'Strong community engagement and transparent creator. ' if overall > 70 else ''}"
                           f"{'Exercise caution and DYOR. ' if overall < 60 else ''}"
                           f"Market conditions appear {'favorable' if market > 70 else 'challenging'}."
            }
        }

        events.append(event)

    return events


def add_graduation_event(event: GraduationEvent):
    """Add a new graduation event"""
    global graduation_events

    event_dict = event.to_dict()
    graduation_events.insert(0, event_dict)  # Add to front

    # Limit storage
    if len(graduation_events) > MAX_EVENTS:
        graduation_events = graduation_events[:MAX_EVENTS]

    save_events()


@app.route('/')
def index():
    """Serve the main webapp"""
    return send_from_directory('.', 'index.html')


@app.route('/styles.css')
def styles():
    """Serve CSS"""
    return send_from_directory('.', 'styles.css')


@app.route('/app.js')
def app_js():
    """Serve JavaScript"""
    return send_from_directory('.', 'app.js')


@app.route('/api/bags-intel/graduations', methods=['GET'])
def get_graduations():
    """Get all graduation events"""
    return jsonify({
        'success': True,
        'events': graduation_events,
        'count': len(graduation_events)
    })


@app.route('/api/bags-intel/graduations/latest', methods=['GET'])
def get_latest_graduation():
    """Get the most recent graduation"""
    if graduation_events:
        return jsonify({
            'success': True,
            'event': graduation_events[0]
        })
    else:
        return jsonify({
            'success': False,
            'error': 'No events available'
        }), 404


@app.route('/api/bags-intel/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""
    if not graduation_events:
        return jsonify({
            'success': True,
            'stats': {
                'total_events': 0,
                'avg_score': 0,
                'quality_distribution': {}
            }
        })

    # Calculate stats
    total = len(graduation_events)
    avg_score = sum(e['scores']['overall'] for e in graduation_events) / total

    quality_dist = {}
    for event in graduation_events:
        quality = event['scores']['quality']
        quality_dist[quality] = quality_dist.get(quality, 0) + 1

    return jsonify({
        'success': True,
        'stats': {
            'total_events': total,
            'avg_score': round(avg_score, 1),
            'quality_distribution': quality_dist
        }
    })


@app.route('/api/bags-intel/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to receive new graduation events from bags_intel service"""
    from flask import request

    try:
        event_data = request.get_json()

        if not event_data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Validate required fields
        if 'token' not in event_data or 'scores' not in event_data:
            return jsonify({
                'success': False,
                'error': 'Invalid event data'
            }), 400

        # Add timestamp if not present
        if 'timestamp' not in event_data:
            event_data['timestamp'] = datetime.utcnow().isoformat()

        # Add to events list
        graduation_events.insert(0, event_data)

        # Limit storage
        if len(graduation_events) > MAX_EVENTS:
            graduation_events[:] = graduation_events[:MAX_EVENTS]

        save_events()

        return jsonify({
            'success': True,
            'message': 'Event received',
            'event_id': event_data.get('token', {}).get('mint', 'unknown')
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'events_count': len(graduation_events),
        'timestamp': datetime.utcnow().isoformat()
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🎯 Bags Intel API Server")
    print("=" * 60)

    # Load existing events or generate mock data
    load_events()

    print(f"\nLoaded {len(graduation_events)} events")
    print("\nStarting server...")
    print("Open: http://localhost:5000")
    print("\nAPI Endpoints:")
    print("  GET  /api/bags-intel/graduations")
    print("  GET  /api/bags-intel/graduations/latest")
    print("  GET  /api/bags-intel/stats")
    print("  GET  /api/health")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)
