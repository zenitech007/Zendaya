"""
IoT Controller Tool - Smart home and device control
"""
import json
from typing import Dict, Any
from langchain.tools import Tool

class IoTTool:
    def __init__(self):
        # Mock IoT devices for demonstration
        self.devices = {
            "lights": {"living_room": False, "bedroom": False, "kitchen": True},
            "thermostat": {"temperature": 72, "mode": "auto"},
            "security": {"armed": False, "cameras": True}
        }
    
    def control_device(self, command: str) -> str:
        """Control IoT devices (mock implementation)"""
        command_lower = command.lower()
        
        # Light controls
        if "light" in command_lower:
            if "turn on" in command_lower or "on" in command_lower:
                room = self._extract_room(command_lower)
                if room in self.devices["lights"]:
                    self.devices["lights"][room] = True
                    return f"Turned on {room} lights."
                return "Turned on all lights."
            
            elif "turn off" in command_lower or "off" in command_lower:
                room = self._extract_room(command_lower)
                if room in self.devices["lights"]:
                    self.devices["lights"][room] = False
                    return f"Turned off {room} lights."
                return "Turned off all lights."
        
        # Thermostat controls
        elif "temperature" in command_lower or "thermostat" in command_lower:
            if "set" in command_lower:
                # Extract temperature (simplified)
                import re
                temp_match = re.search(r'(\d+)', command)
                if temp_match:
                    temp = int(temp_match.group(1))
                    self.devices["thermostat"]["temperature"] = temp
                    return f"Set temperature to {temp}°F."
            
            return f"Current temperature: {self.devices['thermostat']['temperature']}°F"
        
        # Security controls
        elif "security" in command_lower or "alarm" in command_lower:
            if "arm" in command_lower:
                self.devices["security"]["armed"] = True
                return "Security system armed."
            elif "disarm" in command_lower:
                self.devices["security"]["armed"] = False
                return "Security system disarmed."
        
        return f"IoT command processed: {command}"
    
    def _extract_room(self, command: str) -> str:
        """Extract room name from command"""
        rooms = ["living_room", "bedroom", "kitchen", "bathroom"]
        for room in rooms:
            if room.replace("_", " ") in command:
                return room
        return "living_room"  # default
    
    def get_tool(self) -> Tool:
        """Return LangChain tool"""
        return Tool(
            name="iot_control",
            description="Control smart home devices like lights, thermostat, and security systems",
            func=self.control_device
        )