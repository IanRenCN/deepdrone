#!/usr/bin/env python3
"""
DeepDrone Launcher - Starts simulator and web interface together
"""

import sys
import os
import subprocess
import time
import signal
import webbrowser
import threading
from pathlib import Path

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

class DeepDroneLauncher:
    def __init__(self):
        self.simulator_process = None
        self.web_server_process = None

    def open_browser(self):
        """Open browser after a short delay."""
        time.sleep(2)  # Wait for server to start
        webbrowser.open('http://localhost:8000')

    def start_simulator(self):
        """Start the drone simulator in the background."""
        print("🚁 Starting drone simulator...")
        try:
            self.simulator_process = subprocess.Popen(
                [sys.executable, 'simulate_drone.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=current_dir
            )
            print("✓ Simulator started (PID: {})".format(self.simulator_process.pid))
            time.sleep(1)  # Give simulator time to initialize
            return True
        except Exception as e:
            print(f"✗ Failed to start simulator: {e}")
            return False

    def start_web_server(self):
        """Start the web server."""
        print("🌐 Starting web server...")
        try:
            import uvicorn
            from web_server import app

            # Open browser in a separate thread
            browser_thread = threading.Thread(target=self.open_browser, daemon=True)
            browser_thread.start()

            # Start the server (this blocks)
            uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

        except Exception as e:
            print(f"✗ Failed to start web server: {e}")
            import traceback
            traceback.print_exc()
            return False

    def cleanup(self):
        """Clean up processes on exit."""
        print("\n\n🛑 Shutting down...")

        if self.simulator_process:
            print("   Stopping simulator...")
            self.simulator_process.terminate()
            try:
                self.simulator_process.wait(timeout=5)
                print("   ✓ Simulator stopped")
            except subprocess.TimeoutExpired:
                print("   ⚠ Force killing simulator...")
                self.simulator_process.kill()

        print("   ✓ Web server stopped")
        print("\n👋 DeepDrone shutdown complete. Goodbye!\n")

    def run(self):
        """Main launcher."""
        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            self.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Print banner
        print("=" * 70)
        print("🚁 DeepDrone - Complete Launch")
        print("=" * 70)
        print()
        print("This will start:")
        print("  1. 🛩️  Drone Simulator (background)")
        print("  2. 🌐 Web Interface (http://localhost:8000)")
        print()
        print("=" * 70)
        print()

        # Start simulator
        if not self.start_simulator():
            print("\n❌ Failed to start simulator. Exiting...")
            sys.exit(1)

        print()
        print("=" * 70)
        print("✓ All systems ready!")
        print("=" * 70)
        print()
        print("📱 Opening browser at: http://localhost:8000")
        print()
        print("💡 Quick Start Guide:")
        print("   1. Select an AI provider (Ollama for local/free)")
        print("   2. Connection string is pre-filled: udp:127.0.0.1:14550")
        print("   3. Click 'Connect Drone'")
        print("   4. Start chatting with your drone!")
        print()
        print("⚠️  Press Ctrl+C to stop everything")
        print()
        print("=" * 70)
        print()

        # Start web server (this blocks until interrupted)
        try:
            self.start_web_server()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

def main():
    launcher = DeepDroneLauncher()
    launcher.run()

if __name__ == "__main__":
    main()
