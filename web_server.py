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
from drone.webots_drone_adapter import WebotsDroneAdapter
from drone.function_tools import FunctionExecutor, format_function_schemas_for_ollama, FUNCTION_SCHEMAS

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
    """Connect to drone (DroneKit or Webots)."""
    global drone_controller

    try:
        connection_string = request.connection_string.lower()
        print(f"🔌 Attempting to connect to drone at: {request.connection_string}")

        # Detect connection type: Webots UDP or DroneKit
        is_webots = (
            connection_string == "webots" or 
            connection_string.startswith("udp:") and ":9000" in connection_string or
            "webots" in connection_string
        )

        if is_webots:
            print("🎮 Using Webots UDP controller")
            drone_controller = WebotsDroneAdapter(request.connection_string)
        else:
            print("🚁 Using DroneKit controller (MAVLink)")
            drone_controller = DroneController(request.connection_string)

        success = drone_controller.connect_to_drone()

        if success:
            controller_type = "Webots simulator" if is_webots else "drone"
            print(f"✅ Successfully connected to {controller_type}")
            return {
                "status": "success",
                "message": f"Connected to {controller_type} at {request.connection_string}",
                "controller_type": "webots" if is_webots else "dronekit"
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
    if not drone_controller:
        return {"connected": False}
    
    # Check connected status - handle both DroneKit and Webots
    if not drone_controller.connected:
        return {"connected": False}

    try:
        vehicle = drone_controller.vehicle
        if not vehicle:
            # This shouldn't happen, but handle it
            print(f"⚠️  WARNING: Controller connected but vehicle is None")
            return {"connected": False, "error": "Vehicle object not initialized"}
        
        return {
            "connected": True,
            "mode": str(vehicle.mode.name) if hasattr(vehicle.mode, 'name') else str(vehicle.mode),
            "armed": vehicle.armed,
            "battery": vehicle.battery.level if hasattr(vehicle, 'battery') and vehicle.battery else 100.0,
            "altitude": vehicle.location.global_relative_frame.alt if hasattr(vehicle, 'location') and vehicle.location else 0.0,
            "gps": {
                "lat": vehicle.location.global_frame.lat if hasattr(vehicle, 'location') and vehicle.location else 0.0,
                "lon": vehicle.location.global_frame.lon if hasattr(vehicle, 'location') and vehicle.location else 0.0
            }
        }
    except Exception as e:
        # Log the actual error for debugging
        print(f"❌ Error getting drone status: {e}")
        import traceback
        traceback.print_exc()
        return {"connected": False, "error": str(e)}

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    print("✅ WebSocket client connected")
    
    # Create function executor
    function_executor = FunctionExecutor(drone_controller)

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
                
                # Update function executor with current drone controller
                function_executor.drone_controller = drone_controller

                # Get drone context if connected
                drone_context = ""
                if drone_controller and drone_controller.connected:
                    status = await get_drone_status()
                    drone_context = f"\nCurrent Drone Status: {json.dumps(status, indent=2)}"
                    print(f"🚁 Added drone context: connected={status.get('connected', False)}")
                else:
                    print(f"⚠️  Drone not connected (controller exists: {drone_controller is not None}, connected: {drone_controller.connected if drone_controller else False})")

                # Add function schemas for Ollama
                functions_info = ""
                if current_config and current_config.provider == "ollama":
                    functions_info = "\n\n" + format_function_schemas_for_ollama(FUNCTION_SCHEMAS)

                # Create messages for LLM
                # Check connection status for better prompt
                is_connected = drone_controller and drone_controller.connected if drone_controller else False
                connection_note = "The drone IS CONNECTED and ready for commands." if is_connected else "The drone is NOT CONNECTED. Tell the user to connect first."
                
                system_prompt = f"""You are DeepDrone AI, an assistant that controls drones using natural language.

{connection_note}
{drone_context}

IMPORTANT: When the user asks you to perform a drone action (like takeoff, land, fly somewhere, etc.), you MUST execute the appropriate function immediately. Do NOT just provide instructions - actually execute the command.

{functions_info}

When executing commands:
1. ALWAYS check the drone status above - if connected is true, the drone IS ready
2. Use the functions to perform the action
3. After getting the function result, explain what happened to the user in a friendly way

Example of how to execute a function:
User: "Take off to 20 meters"
Your response:
EXECUTE_FUNCTION: arm_and_takeoff
ARGUMENTS: {{"altitude": 20}}"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]

                # Get LLM response
                print(f"⏳ Calling LLM chat method...")
                response_data = await asyncio.to_thread(
                    llm_interface.chat_with_metadata,
                    messages
                )

                print(f"✅ Got LLM response")
                print(f"Response data type: {type(response_data)}")
                print(f"Response data keys: {response_data.keys() if isinstance(response_data, dict) else 'NOT A DICT'}")
                
                # Check if response contains a function call
                response_content = response_data.get("content", "") if isinstance(response_data, dict) else str(response_data)
                print(f"Response content preview (first 200 chars): {response_content[:200]}")
                
                # Parse function calls from response
                if "EXECUTE_FUNCTION:" in response_content:
                    print("🔧 Function call detected in response")
                    
                    # Extract function name and arguments
                    lines = response_content.split('\n')
                    function_name = None
                    arguments = {}
                    
                    for i, line in enumerate(lines):
                        if line.startswith("EXECUTE_FUNCTION:"):
                            function_name = line.replace("EXECUTE_FUNCTION:", "").strip()
                        elif line.startswith("ARGUMENTS:"):
                            try:
                                args_str = line.replace("ARGUMENTS:", "").strip()
                                arguments = json.loads(args_str) if args_str else {}
                            except json.JSONDecodeError:
                                print(f"⚠️  Failed to parse arguments: {line}")
                    
                    if function_name:
                        print(f"⚡ Executing function: {function_name} with args: {arguments}")
                        
                        # Execute the function
                        result = await asyncio.to_thread(
                            function_executor.execute_function,
                            function_name,
                            arguments
                        )
                        
                        print(f"✅ Function result: {result}")
                        
                        # Ask LLM to format the result for the user
                        follow_up_prompt = f"""The function {function_name} was executed with result: {json.dumps(result)}

Please explain this result to the user in a natural, friendly way. Be concise."""
                        
                        messages.append({"role": "assistant", "content": response_content})
                        messages.append({"role": "user", "content": follow_up_prompt})
                        
                        # Get formatted response
                        final_response_data = await asyncio.to_thread(
                            llm_interface.chat_with_metadata,
                            messages
                        )
                        
                        response_data = final_response_data

                # Send AI response
                if response_data and isinstance(response_data, dict) and response_data.get("content"):
                    # Prepare metadata (thinking info)
                    metadata = {}
                    if response_data.get("thinking"):
                        metadata["thinking"] = response_data["thinking"]
                        metadata["thinking_time"] = response_data.get("thinking_time", 0)
                    
                    content_to_send = response_data["content"]
                    print(f"📤 Sending content to client (length: {len(content_to_send)}, preview: {content_to_send[:100]})")
                    
                    await websocket.send_json({
                        "type": "ai_message",
                        "content": content_to_send,
                        "metadata": metadata if metadata else None
                    })
                    print(f"📤 Sent response to client successfully")
                else:
                    print(f"⚠️  Empty response from LLM!")
                    await websocket.send_json({
                        "type": "error",
                        "content": "Received empty response from AI model"
                    })

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
