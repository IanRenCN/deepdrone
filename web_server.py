#!/usr/bin/env python3
"""
DeepDrone Web Server - Browser-based Chat Interface
FastAPI server with WebSocket support for real-time drone control.
"""

import os
import json
import asyncio
import subprocess
from typing import Optional, Dict, List
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from drone.config import ModelConfig
from drone.llm_interface import LLMInterface
from drone.drone_control import DroneController

# Load environment variables
load_dotenv()

app = FastAPI(title="DeepDrone", description="AI-Powered Drone Control System")

# Global state
drone_controller: Optional[DroneController] = None
llm_interface: Optional[LLMInterface] = None
current_config: Optional[ModelConfig] = None

# Pydantic models for API
class ConfigRequest(BaseModel):
    provider: str  # "openai", "anthropic", "google", "ollama"
    api_key: Optional[str] = None
    model: str

class DroneConnectionRequest(BaseModel):
    connection_string: str  # e.g., "udp:127.0.0.1:14550"

class ChatMessage(BaseModel):
    message: str

@app.get("/")
async def read_root():
    """Serve the main HTML page."""
    return FileResponse("static/index.html")

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "drone_connected": drone_controller is not None and drone_controller.connected if drone_controller else False,
        "llm_configured": llm_interface is not None
    }

@app.get("/api/ollama/models")
async def get_ollama_models():
    """Get list of locally installed Ollama models."""
    try:
        # Run ollama list command
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {"models": [], "error": "Ollama not installed or not running"}

        # Parse the output
        lines = result.stdout.strip().split('\n')
        if len(lines) <= 1:
            return {"models": []}

        # Skip header line and parse model names
        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                model_name = parts[0]
                models.append(model_name)

        return {"models": models}

    except subprocess.TimeoutExpired:
        return {"models": [], "error": "Ollama command timed out"}
    except FileNotFoundError:
        return {"models": [], "error": "Ollama not installed"}
    except Exception as e:
        return {"models": [], "error": str(e)}

@app.post("/api/config")
async def configure_ai(config: ConfigRequest):
    """Configure AI provider and model."""
    global llm_interface, current_config

    try:
        # Create model config with required fields
        model_config = ModelConfig(
            name=f"{config.provider}-{config.model.split('/')[-1]}",
            provider=config.provider,
            model_id=config.model,
            api_key=config.api_key or os.getenv(f"{config.provider.upper()}_API_KEY"),
            base_url="http://localhost:11434" if config.provider == "ollama" else None
        )

        # Initialize LLM interface
        llm_interface = LLMInterface(model_config)
        current_config = model_config

        return {
            "status": "success",
            "message": f"Configured {config.provider} with model {config.model}"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/drone/connect")
async def connect_drone(request: DroneConnectionRequest):
    """Connect to drone."""
    global drone_controller

    try:
        print(f"🔌 Attempting to connect to drone at: {request.connection_string}")

        drone_controller = DroneController(request.connection_string)
        success = drone_controller.connect_to_drone()

        if success:
            print(f"✅ Successfully connected to drone")
            return {
                "status": "success",
                "message": f"Connected to drone at {request.connection_string}"
            }
        else:
            error_msg = "Failed to connect to drone. Make sure the simulator is running (should be started automatically by start.sh)"
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

    except Exception as e:
        error_msg = f"Connection error: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()

        # Provide helpful error messages
        if "Connection refused" in str(e):
            error_msg = "Connection refused. Make sure the simulator is running (should be started automatically by start.sh)"
        elif "timeout" in str(e).lower():
            error_msg = "Connection timeout. The simulator may not be responding. Check if it's running on " + request.connection_string

        raise HTTPException(status_code=400, detail=error_msg)

@app.post("/api/drone/disconnect")
async def disconnect_drone():
    """Disconnect from drone."""
    global drone_controller

    if drone_controller:
        try:
            if drone_controller.vehicle:
                drone_controller.vehicle.close()
            drone_controller = None
            return {"status": "success", "message": "Disconnected from drone"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "message": "No drone connected"}

@app.get("/api/drone/status")
async def get_drone_status():
    """Get current drone status."""
    if not drone_controller or not drone_controller.connected:
        return {"connected": False}

    try:
        vehicle = drone_controller.vehicle
        return {
            "connected": True,
            "mode": str(vehicle.mode.name),
            "armed": vehicle.armed,
            "battery": vehicle.battery.level if vehicle.battery else None,
            "altitude": vehicle.location.global_relative_frame.alt if vehicle.location else None,
            "gps": {
                "lat": vehicle.location.global_frame.lat if vehicle.location else None,
                "lon": vehicle.location.global_frame.lon if vehicle.location else None
            }
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    print("✅ WebSocket client connected")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")

            print(f"📨 Received message: {user_message}")

            # Send user message acknowledgment
            await websocket.send_json({
                "type": "user_message",
                "content": user_message
            })

            # Check if LLM is configured
            if not llm_interface:
                print("❌ LLM not configured")
                await websocket.send_json({
                    "type": "error",
                    "content": "Please configure an AI provider first"
                })
                continue

            # Process with LLM
            try:
                print(f"🤖 Processing with LLM...")

                # Get drone context if connected
                drone_context = ""
                if drone_controller and drone_controller.connected:
                    status = await get_drone_status()
                    drone_context = f"\nDrone Status: {json.dumps(status, indent=2)}"
                    print(f"🚁 Added drone context")

                # Create messages for LLM
                system_prompt = f"""You are DeepDrone AI, an assistant that helps control drones using natural language.
You can help with:
- Connecting to drones
- Flight commands (takeoff, land, movement)
- Flight patterns and waypoints
- Safety operations (emergency stop, return to home)
{drone_context}

When the user wants to perform a drone action, provide clear, step-by-step instructions.
If the drone is not connected, guide them to connect first."""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]

                # Get LLM response
                print(f"⏳ Calling LLM chat method...")
                response = await asyncio.to_thread(
                    llm_interface.chat,
                    messages
                )

                print(f"✅ Got LLM response: {response[:100]}...")

                # Send AI response
                await websocket.send_json({
                    "type": "ai_message",
                    "content": response
                })

                print(f"📤 Sent response to client")

            except Exception as e:
                print(f"❌ Error processing message: {str(e)}")
                import traceback
                traceback.print_exc()

                await websocket.send_json({
                    "type": "error",
                    "content": f"Error processing message: {str(e)}"
                })

    except WebSocketDisconnect:
        print("🔌 Client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.close()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn

    print("🚁 Starting DeepDrone Web Server...")
    print("📡 Open your browser at: http://localhost:8000")

    uvicorn.run(app, host="0.0.0.0", port=8000)
