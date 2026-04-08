"""
Render deployment entry point
Starts trading bot + orchestrator + dashboard web server
"""

import subprocess
import threading
import time
import os
import json
from flask import Flask, send_file, jsonify

app = Flask(__name__)

def start_bot():
    """Run trading bot in background"""
    try:
        subprocess.run(['python', 'trading_bot_alpaca_integration.py'])
    except Exception as e:
        print(f"Bot error: {e}")

def start_orchestrator():
    """Run orchestrator in background"""
    try:
        subprocess.run(['python', 'ai_singularity_orchestrator.py'])
    except Exception as e:
        print(f"Orchestrator error: {e}")

@app.route('/')
def dashboard():
    """Serve dashboard HTML"""
    try:
        return send_file('ai_orchestrator_dashboard.html')
    except Exception as e:
        return f"Dashboard error: {e}", 500

@app.route('/api/metrics')
def metrics():
    """Serve latest metrics as JSON"""
    try:
        # Try to read metrics file
        with open('ai_metrics_latest.json', 'r') as f:
            data = json.load(f)
            return jsonify(data)
    except FileNotFoundError:
        # Return default metrics while system initializes
        return jsonify({
            'status': 'initializing',
            'orchestrator_status': 'INITIALIZING',
            'bot_status': 'WAITING',
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'total_pnl': 0,
            'current_drawdown': 0.0,
            'active_assets': 40,
            'daily_signals': 0,
            'uptime_seconds': 0,
            'api_latency': 150,
            'message': 'System initializing...'
        })
    except Exception as e:
        # Return error metrics
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/status')
def status():
    """Health check endpoint"""
    return jsonify({'status': 'running', 'message': 'Trading bot is active'})

if __name__ == '__main__':
    print("Starting trading system...")

    # Start bot and orchestrator in background threads
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    orch_thread = threading.Thread(target=start_orchestrator, daemon=True)

    print("Launching bot...")
    bot_thread.start()

    print("Launching orchestrator...")
    orch_thread.start()

    # Give them time to initialize
    time.sleep(5)

    # Start web server on Render port
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
