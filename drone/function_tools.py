"""
Function calling tools for LLM to execute drone commands.
"""

import json
from typing import Dict, List, Any, Optional
from .drone_control import DroneController

# Define function schemas for LLMs
FUNCTION_SCHEMAS = [
    {
        "name": "arm_and_takeoff",
        "description": "Arm the drone and take off to a specified altitude. The drone must be connected first.",
        "parameters": {
            "type": "object",
            "properties": {
                "altitude": {
                    "type": "number",
                    "description": "Target altitude in meters (e.g., 20 for 20 meters)"
                }
            },
            "required": ["altitude"]
        }
    },
    {
        "name": "land",
        "description": "Land the drone at its current location.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "return_to_launch",
        "description": "Return the drone to its launch/home location and land.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "goto_location",
        "description": "Fly the drone to a specific GPS coordinate at a given altitude.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Target latitude in decimal degrees"
                },
                "longitude": {
                    "type": "number",
                    "description": "Target longitude in decimal degrees"
                },
                "altitude": {
                    "type": "number",
                    "description": "Target altitude in meters"
                }
            },
            "required": ["latitude", "longitude", "altitude"]
        }
    },
    {
        "name": "get_status",
        "description": "Get the current status of the drone including mode, armed state, altitude, battery, and GPS location.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "set_airspeed",
        "description": "Set the target airspeed of the drone.",
        "parameters": {
            "type": "object",
            "properties": {
                "speed": {
                    "type": "number",
                    "description": "Target airspeed in m/s"
                }
            },
            "required": ["speed"]
        }
    }
]

class FunctionExecutor:
    """Executes function calls from LLM on the drone."""
    
    def __init__(self, drone_controller: Optional[DroneController] = None):
        self.drone_controller = drone_controller
    
    def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a function call and return the result."""
        
        if not self.drone_controller:
            return {
                "success": False,
                "error": "Drone not connected. Please connect to the drone first."
            }
        
        try:
            if function_name == "arm_and_takeoff":
                altitude = arguments.get("altitude")
                if not altitude:
                    return {"success": False, "error": "Missing altitude parameter"}
                
                success = self.drone_controller.arm_and_takeoff(altitude)
                return {
                    "success": success,
                    "message": f"Successfully took off to {altitude}m! The drone is now airborne." if success else "Takeoff failed. The drone may need more time for GPS lock or system initialization."
                }
            
            elif function_name == "land":
                success = self.drone_controller.land()
                return {
                    "success": success,
                    "message": "Landing initiated" if success else "Landing failed"
                }
            
            elif function_name == "return_to_launch":
                success = self.drone_controller.return_to_launch()
                return {
                    "success": success,
                    "message": "Returning to launch point" if success else "Return to launch failed"
                }
            
            elif function_name == "goto_location":
                lat = arguments.get("latitude")
                lon = arguments.get("longitude")
                alt = arguments.get("altitude")
                
                if lat is None or lon is None or alt is None:
                    return {"success": False, "error": "Missing location parameters"}
                
                success = self.drone_controller.goto_location(lat, lon, alt)
                return {
                    "success": success,
                    "message": f"Flying to ({lat}, {lon}) at {alt}m" if success else "Navigation failed"
                }
            
            elif function_name == "get_status":
                if not self.drone_controller.vehicle:
                    return {"success": False, "error": "Vehicle not available"}
                
                vehicle = self.drone_controller.vehicle
                status = {
                    "success": True,
                    "mode": str(vehicle.mode.name),
                    "armed": vehicle.armed,
                    "altitude": vehicle.location.global_relative_frame.alt if vehicle.location else None,
                    "battery": vehicle.battery.level if vehicle.battery else None,
                    "gps": {
                        "lat": vehicle.location.global_frame.lat if vehicle.location else None,
                        "lon": vehicle.location.global_frame.lon if vehicle.location else None
                    }
                }
                return status
            
            elif function_name == "set_airspeed":
                speed = arguments.get("speed")
                if not speed:
                    return {"success": False, "error": "Missing speed parameter"}
                
                success = self.drone_controller.set_airspeed(speed)
                return {
                    "success": success,
                    "message": f"Airspeed set to {speed} m/s" if success else "Failed to set airspeed"
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unknown function: {function_name}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing {function_name}: {str(e)}"
            }


def format_function_schemas_for_ollama(schemas: List[Dict]) -> str:
    """Format function schemas as a string for Ollama (which doesn't support native function calling)."""
    functions_desc = "You have access to the following drone control functions:\n\n"
    
    for func in schemas:
        functions_desc += f"**{func['name']}**\n"
        functions_desc += f"Description: {func['description']}\n"
        
        if func['parameters']['properties']:
            functions_desc += "Parameters:\n"
            for param_name, param_info in func['parameters']['properties'].items():
                required = " (required)" if param_name in func['parameters'].get('required', []) else ""
                functions_desc += f"  - {param_name}: {param_info.get('description', 'No description')}{required}\n"
        else:
            functions_desc += "Parameters: None\n"
        
        functions_desc += "\n"
    
    functions_desc += """To execute a function, respond with:
EXECUTE_FUNCTION: function_name
ARGUMENTS: {"param1": value1, "param2": value2}

After executing the function, I will provide you with the result, and you should explain it to the user in natural language.
"""
    
    return functions_desc

