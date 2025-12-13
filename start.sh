#!/bin/bash

# DeepDrone Launcher Script
# Starts both simulator and web interface

echo "======================================================================"
echo "🚁 DeepDrone - Complete Launch"
echo "======================================================================"
echo ""
echo "This will start:"
echo "  1. 🛩️  Drone Simulator (background)"
echo "  2. 🌐 Web Interface (http://localhost:8000)"
echo ""
echo "======================================================================"
echo ""

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Clean up ports before starting
echo "🧹 Cleaning up ports..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5760 | xargs kill -9 2>/dev/null || true
pkill -f simple_simulator.py 2>/dev/null || true
sleep 1
echo "✓ Ports cleaned"
echo ""

# Start simulator in background
echo "🚁 Starting drone simulator..."
python3 simple_simulator.py > /tmp/deepdrone_simulator.log 2>&1 &
SIMULATOR_PID=$!
echo "✓ Simulator started (PID: $SIMULATOR_PID)"
echo ""

# Wait a moment for simulator to initialize
sleep 2

# Function to cleanup on exit
cleanup() {
    echo ""
    echo ""
    echo "🛑 Shutting down..."
    echo "   Stopping simulator (PID: $SIMULATOR_PID)..."
    kill $SIMULATOR_PID 2>/dev/null
    wait $SIMULATOR_PID 2>/dev/null
    echo "   ✓ Simulator stopped"
    echo "   ✓ Web server stopped"
    echo ""
    echo "👋 DeepDrone shutdown complete. Goodbye!"
    echo ""
    exit 0
}

# Set up trap to catch Ctrl+C
trap cleanup INT TERM

echo "======================================================================"
echo "✓ All systems ready!"
echo "======================================================================"
echo ""
echo "📱 Opening browser at: http://localhost:8000"
echo ""
echo "💡 Quick Start Guide:"
echo "   1. Select an AI provider (Ollama for local/free)"
echo "   2. Connection string is pre-filled: tcp:127.0.0.1:5760"
echo "   3. Click 'Connect Drone'"
echo "   4. Start chatting with your drone!"
echo ""
echo "⚠️  Press Ctrl+C to stop everything"
echo ""
echo "======================================================================"
echo ""

# Start web server (this will block)
python3 main.py

# If we get here, cleanup
cleanup
