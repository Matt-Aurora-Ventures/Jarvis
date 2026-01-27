#!/bin/bash
# Start both Jarvis web interfaces in parallel

echo "🚀 Starting Jarvis Web Interfaces..."
echo ""
echo "📊 Trading Interface: http://127.0.0.1:5001"
echo "⚙️  Control Deck:      http://127.0.0.1:5000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to kill all background jobs on exit
cleanup() {
    echo ""
    echo "🛑 Stopping web servers..."
    jobs -p | xargs kill 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start trading interface
python trading_web.py &
TRADING_PID=$!

# Start control deck
python task_web.py &
CONTROL_PID=$!

# Wait for both processes
wait $TRADING_PID $CONTROL_PID
