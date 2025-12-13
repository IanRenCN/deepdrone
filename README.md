# 🚁 DeepDrone - AI-Powered Drone Control

![DeepDrone Demo](media/demo.png)

**Control drones with natural language using AI models like OpenAI, Anthropic, Google, and local Ollama models - now with a beautiful web interface!**

## 🚀 Quick Start

### **One-Command Launch** (Easiest!)

```bash
# Install dependencies (first time only)
pip3 install -r requirements.txt

# Start everything (simulator + web interface)
python3 start.py
# or use: ./start.sh
```

This automatically starts:
- ✅ Drone simulator in the background
- ✅ Web interface at http://localhost:8000
- ✅ Opens your browser automatically

### **Manual Launch** (Advanced)

```bash
# Terminal 1: Start simulator
python3 simulate_drone.py

# Terminal 2: Start web interface
python3 main.py
```

The web interface features:
- **🎨 Modern Browser UI**: Clean, intuitive chat interface
- **⚙️ Easy Configuration**: Configure AI providers in the left sidebar
- **🤖 Multiple AI Providers**: OpenAI, Anthropic, Google, or local Ollama
- **📊 Live Telemetry**: Real-time drone status and metrics
- **💬 Natural Language Control**: Chat with your drone like a copilot

## ✨ Features

- 🌐 **Web Interface**: Beautiful browser-based chat UI with dark theme
- 🤖 **Multi-AI Support**: OpenAI, Anthropic, Google, or local Ollama models
- 🚁 **Real Drone Control**: DroneKit integration for actual flight control
- 💬 **Natural Language**: Control drones with conversational commands
- 📊 **Live Telemetry**: Real-time altitude, battery, GPS, and status
- 🛠️ **Built-in Simulator**: Includes drone simulator for testing
- 🔒 **Safe Operations**: Emergency stops and return-to-home functions
- 🔌 **Auto Model Detection**: Automatically detects installed Ollama models

## 🛠️ Simulator Setup

```bash
# In a separate terminal, start the simulator:
python3 simulate_drone.py

# Then in the web interface:
# 1. Configure your AI provider (e.g., select Ollama for local use)
# 2. Enter connection string: udp:127.0.0.1:14550
# 3. Click "Connect Drone"
# 4. Start chatting with your drone!
```

## 📝 Example Commands

Simply chat naturally with your drone:

```
💬 "Take off to 20 meters"
💬 "Fly to GPS coordinates 37.7749, -122.4194"
💬 "Execute a square flight pattern with 50m sides"
💬 "What's my current altitude and battery level?"
💬 "Return home and land safely"
```

## 🔧 Requirements

- Python 3.8+
- DroneKit-Python
- LiteLLM for cloud models
- Ollama for local models (optional)

## 🖥️ CLI Mode (Optional)

Prefer the terminal? The classic CLI mode is still available:

```bash
python3 main.py --cli
```

## 💻 Tech Stack

**Backend:**
- **FastAPI** - Modern async web framework with WebSocket support
- **LiteLLM** - Unified interface for cloud AI models (OpenAI, Anthropic, Google)
- **Ollama** - Local AI model execution and management
- **DroneKit-Python** - Real drone control and telemetry
- **Uvicorn** - High-performance ASGI server

**Frontend:**
- **Pure JavaScript** - No frameworks, fast and lightweight
- **WebSocket** - Real-time bidirectional communication
- **Modern CSS** - Beautiful dark theme with responsive design

**Configuration:**
- **Pydantic** - Configuration management and validation
- **python-dotenv** - Environment variable management

## 📸 Screenshots

The web interface includes:
- **Left Sidebar**: AI provider configuration, drone connection, live telemetry
- **Chat Area**: Natural language conversation with your drone
- **Real-time Updates**: WebSocket-powered instant communication
- **Status Indicators**: Visual feedback for AI and drone connection status