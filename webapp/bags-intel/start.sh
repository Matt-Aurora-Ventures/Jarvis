#!/bin/bash

echo "================================================"
echo "Bags Intel Webapp - JARVIS LifeOS"
echo "================================================"
echo ""
echo "Checking Python..."
python3 --version
echo ""

echo "Installing dependencies..."
pip3 install -r requirements.txt
echo ""

echo "Starting server..."
echo "Open http://localhost:5000 in your browser"
echo ""
echo "Press Ctrl+C to stop the server"
echo "================================================"
echo ""

python3 websocket_server.py
