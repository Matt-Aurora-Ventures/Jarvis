"""
Enhanced Bags Intel API Server with WebSocket support
Real-time updates pushed to connected clients
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Import the event management from api.py
import api

# Import supervisor integration
try:
    from supervisor_integration import get_supervisor_bridge, IntelligenceSharing
    SUPERVISOR_AVAILABLE = True
except ImportError:
    SUPERVISOR_AVAILABLE = False
    get_supervisor_bridge = None

import asyncio

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Use the storage from api module
graduation_events = api.graduation_events

# Get supervisor bridge for cross-component communication
supervisor_bridge = get_supervisor_bridge() if SUPERVISOR_AVAILABLE else None


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


# Intelligence Dashboard routes
@app.route('/intelligence-report.html')
def intelligence_report():
    """Serve intelligence dashboard"""
    return send_from_directory('.', 'intelligence-report.html')


@app.route('/intelligence-app.js')
def intelligence_app_js():
    """Serve intelligence dashboard JavaScript"""
    return send_from_directory('.', 'intelligence-app.js')


@app.route('/intelligence-styles.css')
def intelligence_styles():
    """Serve intelligence dashboard CSS"""
    return send_from_directory('.', 'intelligence-styles.css')


# Enhanced feed routes
@app.route('/index-enhanced.html')
def index_enhanced():
    """Serve enhanced feed"""
    return send_from_directory('.', 'index-enhanced.html')


@app.route('/app-enhanced.js')
def app_enhanced_js():
    """Serve enhanced feed JavaScript"""
    return send_from_directory('.', 'app-enhanced.js')


@app.route('/styles-enhanced.css')
def styles_enhanced():
    """Serve enhanced feed CSS"""
    return send_from_directory('.', 'styles-enhanced.css')


@app.route('/api/bags-intel/graduations', methods=['GET'])
def get_graduations():
    """Get all graduation events"""
    return jsonify({
        'success': True,
        'events': api.graduation_events,
        'count': len(api.graduation_events)
    })


@app.route('/api/bags-intel/graduations/latest', methods=['GET'])
def get_latest_graduation():
    """Get the most recent graduation"""
    if api.graduation_events:
        return jsonify({
            'success': True,
            'event': api.graduation_events[0]
        })
    else:
        return jsonify({
            'success': False,
            'error': 'No events available'
        }), 404


@app.route('/api/bags-intel/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to receive new graduation events from bags_intel service"""
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
        api.graduation_events.insert(0, event_data)

        # Limit storage
        if len(api.graduation_events) > api.MAX_EVENTS:
            api.graduation_events[:] = api.graduation_events[:api.MAX_EVENTS]

        api.save_events()

        # Broadcast to all connected WebSocket clients
        socketio.emit('new_graduation', event_data, broadcast=True)

        # Share intelligence with supervisor if available
        intel_shared = False
        if supervisor_bridge:
            try:
                # Run async intelligence sharing in thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                intel = loop.run_until_complete(
                    supervisor_bridge.share_intelligence(event_data, ai_reasoning=True)
                )
                loop.close()
                intel_shared = True
                print(f"[Supervisor] Shared intel for {event_data.get('token_name', 'unknown')}: {intel.recommendation}")
            except Exception as e:
                print(f"[Supervisor] Failed to share intelligence: {e}")

        return jsonify({
            'success': True,
            'message': 'Event received and broadcast',
            'event_id': event_data.get('token', {}).get('mint', 'unknown'),
            'intelligence_shared': intel_shared
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bags-intel/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""
    if not api.graduation_events:
        return jsonify({
            'success': True,
            'stats': {
                'total_events': 0,
                'avg_score': 0,
                'quality_distribution': {}
            }
        })

    # Calculate stats
    total = len(api.graduation_events)
    avg_score = sum(e['scores']['overall'] for e in api.graduation_events) / total

    quality_dist = {}
    for event in api.graduation_events:
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


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'events_count': len(api.graduation_events),
        'timestamp': datetime.utcnow().isoformat(),
        'websocket': 'enabled',
        'supervisor': SUPERVISOR_AVAILABLE
    })


@app.route('/api/bags-intel/feedback', methods=['POST'])
def receive_feedback():
    """Receive feedback from treasury bot or other components about trading outcomes"""
    if not supervisor_bridge:
        return jsonify({
            'success': False,
            'error': 'Supervisor integration not available'
        }), 503

    try:
        from supervisor_integration import IntelligenceFeedback

        feedback_data = request.get_json()

        # Validate required fields
        required_fields = ['contract_address', 'token_name', 'action_taken', 'outcome']
        missing = [f for f in required_fields if f not in feedback_data]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {missing}'
            }), 400

        # Create feedback object
        feedback = IntelligenceFeedback(
            contract_address=feedback_data['contract_address'],
            token_name=feedback_data['token_name'],
            token_symbol=feedback_data.get('symbol', 'UNKNOWN'),
            our_score=feedback_data.get('our_score', 0),
            action_taken=feedback_data['action_taken'],
            action_timestamp=datetime.fromisoformat(feedback_data.get('action_timestamp', datetime.now().isoformat())),
            entry_price=feedback_data.get('entry_price'),
            exit_price=feedback_data.get('exit_price'),
            outcome=feedback_data['outcome'],
            profit_loss_percent=feedback_data.get('profit_loss_percent'),
            notes=feedback_data.get('notes', '')
        )

        # Process feedback async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(supervisor_bridge.receive_feedback(feedback))
        loop.close()

        print(f"[Feedback] Processed: {feedback.token_name} ({feedback.outcome}) - Accuracy: {supervisor_bridge.prediction_accuracy:.1%}")

        return jsonify({
            'success': True,
            'message': 'Feedback processed',
            'prediction_accuracy': supervisor_bridge.prediction_accuracy,
            'total_predictions': supervisor_bridge.total_predictions
        })

    except Exception as e:
        print(f"[Feedback] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bags-intel/supervisor/stats', methods=['GET'])
def supervisor_stats():
    """Get supervisor integration stats"""
    if not supervisor_bridge:
        return jsonify({
            'success': False,
            'error': 'Supervisor integration not available'
        }), 503

    try:
        stats = supervisor_bridge.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/bags-intel/research/<contract_address>', methods=['GET'])
def get_token_research(contract_address):
    """Get comprehensive research on token and founder"""
    try:
        # Find token in events
        token_event = next(
            (e for e in api.graduation_events
             if e.get('contract_address') == contract_address),
            None
        )

        if not token_event:
            return jsonify({
                'success': False,
                'error': 'Token not found'
            }), 404

        # Import research module
        from founder_research import research_token_comprehensive

        # Run research
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        research = loop.run_until_complete(
            research_token_comprehensive(token_event)
        )
        loop.close()

        return jsonify({
            'success': True,
            'contract_address': contract_address,
            'research': research
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connection"""
    print(f"[WS] Client connected")
    emit('connected', {'message': 'Connected to Bags Intel feed'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print(f"[WS] Client disconnected")


@socketio.on('request_update')
def handle_update_request():
    """Handle client request for latest data"""
    if api.graduation_events:
        emit('update', {
            'events': api.graduation_events[:10],  # Send latest 10
            'count': len(api.graduation_events)
        })


if __name__ == '__main__':
    print("=" * 60)
    print("Bags Intel API Server (WebSocket Enabled)")
    print("=" * 60)

    # Load existing events or generate mock data
    api.load_events()

    print(f"\nLoaded {len(api.graduation_events)} events")
    print("\nStarting server...")
    print("Open: http://localhost:5000")
    print("\nAPI Endpoints:")
    print("  GET  /api/bags-intel/graduations")
    print("  GET  /api/bags-intel/graduations/latest")
    print("  POST /api/bags-intel/webhook")
    print("  GET  /api/bags-intel/stats")
    print("  GET  /api/health")
    print("\nWebSocket Events:")
    print("  connect          - Client connected")
    print("  new_graduation   - New event broadcast")
    print("  request_update   - Request latest data")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
