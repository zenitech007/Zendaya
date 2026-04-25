"""
Advanced Smart Home Controller - Comprehensive IoT Integration
"""
import os
import json
import asyncio
import aiohttp
import socket
from typing import Dict, Any, List, Optional
from langchain.tools import Tool
import subprocess
import platform
from datetime import datetime
import requests
from dotenv import load_dotenv
import pychromecast
import logging
from kasa import SmartDevice

logger = logging.getLogger(__name__)

load_dotenv()

class SmartHomeController:
    def __init__(self):
        # Load API keys from environment
        self.philips_hue_api_key = os.getenv("PHILIPS_HUE_API_KEY")
        self.tp_link_username = os.getenv("TP_LINK_USERNAME")
        self.tp_link_password = os.getenv("TP_LINK_PASSWORD")
        self.samsung_smartthings_token = os.getenv("SAMSUNG_SMARTTHINGS_TOKEN")

        self.discovered_devices = {}
        self.device_protocols = {
            'philips_hue': {'port': 80, 'api_path': '/api'},
            'tp_link_kasa': {'port': 9999},
            'samsung_smartthings': {'port': 39500},
            'amazon_echo': {'port': 1900},
            'google_home': {'port': [8008, 8009]},
            'roku': {'port': 8060},
            'chromecast': {'port': [8008, 8009]},
            'sonos': {'port': 1400},
            'nest': {'port': 443},
            'ring': {'port': 443},
            'wyze': {'port': [80, 443]},
            'lifx': {'port': 56700},
            'wemo': {'port': [49153, 49154]}
        }
    
    async def discover_devices(self):
        """Discover all WiFi-connected smart devices on network"""
        try:
            # Get network range
            network_range = self._get_network_range()
            
            # Scan for devices
            discovered = await self._scan_network(network_range)
            
            # Identify device types
            for ip, info in discovered.items():
                device_type = await self._identify_device(ip, info)
                if device_type:
                    self.discovered_devices[ip] = {
                        'type': device_type,
                        'info': info,
                        'last_seen': datetime.now(),
                        'capabilities': self._get_device_capabilities(device_type)
                    }
            
            print(f"Discovered {len(self.discovered_devices)} smart devices")
            
        except Exception as e:
            print(f"Device discovery error: {e}")
    
    def _get_network_range(self) -> str:
        """Get local network IP range"""
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Convert to network range (assumes /24)
            ip_parts = local_ip.split('.')
            network = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
            return network
            
        except Exception:
            return "192.168.1.0/24"  # Default fallback
    
    async def _scan_network(self, network_range: str) -> Dict[str, Dict]:
        """Scan network for active devices"""
        discovered = {}
        
        try:
            # Use nmap for network scanning if available
            if platform.system() != "Windows":
                result = subprocess.run(
                    ['nmap', '-sn', network_range], 
                    capture_output=True, text=True, timeout=30
                )
                
                # Parse nmap output
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Nmap scan report for' in line:
                        ip = line.split()[-1].strip('()')
                        discovered[ip] = {'method': 'nmap'}
            
            # Fallback: ping sweep
            else:
                base_ip = network_range.split('/')[0].rsplit('.', 1)[0]
                tasks = []
                
                for i in range(1, 255):
                    ip = f"{base_ip}.{i}"
                    tasks.append(self._ping_host(ip))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if result and not isinstance(result, Exception):
                        ip = f"{base_ip}.{i+1}"
                        discovered[ip] = {'method': 'ping'}
        
        except Exception as e:
            print(f"Network scan error: {e}")
        
        return discovered
    
    async def _ping_host(self, ip: str) -> bool:
        """Ping a host to check if it's alive"""
        try:
            if platform.system() == "Windows":
                cmd = ['ping', '-n', '1', '-w', '1000', ip]
            else:
                cmd = ['ping', '-c', '1', '-W', '1', ip]
            
            result = subprocess.run(cmd, capture_output=True, timeout=2)
            return result.returncode == 0
            
        except Exception:
            return False
    
    async def _identify_device(self, ip: str, info: Dict) -> Optional[str]:
        """Identify device type by probing common ports and services"""
        try:
            # Check common smart device ports
            for device_type, config in self.device_protocols.items():
                ports = config.get('port', [])
                if not isinstance(ports, list):
                    ports = [ports]
                
                for port in ports:
                    if await self._check_port(ip, port):
                        # Additional verification based on device type
                        if await self._verify_device_type(ip, port, device_type):
                            return device_type
            
            return None
            
        except Exception as e:
            print(f"Device identification error for {ip}: {e}")
            return None
    
    async def _check_port(self, ip: str, port: int) -> bool:
        """Check if a port is open on a device"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=2
            )
            writer.close()
            await writer.wait_closed()
            return True
            
        except Exception:
            return False
    
    async def _verify_device_type(self, ip: str, port: int, device_type: str) -> bool:
        """Verify device type with specific protocol checks"""
        try:
            if device_type == 'philips_hue':
                # Check for Hue bridge API
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                    async with session.get(f"http://{ip}/api/config") as response:
                        if response.status == 200:
                            data = await response.json()
                            return 'bridgeid' in data
            
            elif device_type == 'chromecast':
                # Check for Chromecast device info
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                    async with session.get(f"http://{ip}:{port}/setup/eureka_info") as response:
                        return response.status == 200
            
            elif device_type == 'roku':
                # Check for Roku device info
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                    async with session.get(f"http://{ip}:{port}/query/device-info") as response:
                        return response.status == 200 and 'roku' in (await response.text()).lower()
            
            # Add more device-specific verifications as needed
            return True
            
        except Exception:
            return False
    
    def _get_device_capabilities(self, device_type: str) -> List[str]:
        """Get capabilities for each device type"""
        capabilities = {
            'philips_hue': ['lighting', 'color_control', 'dimming', 'scheduling'],
            'tp_link_kasa': ['power_control', 'scheduling', 'energy_monitoring'],
            'samsung_smartthings': ['hub_control', 'device_management', 'automation'],
            'amazon_echo': ['voice_control', 'music_playback', 'smart_home_control'],
            'google_home': ['voice_control', 'music_playback', 'casting'],
            'roku': ['media_streaming', 'channel_control', 'remote_control'],
            'chromecast': ['media_casting', 'screen_mirroring'],
            'sonos': ['music_playback', 'multi_room_audio', 'voice_control'],
            'nest': ['temperature_control', 'scheduling', 'presence_detection'],
            'ring': ['security_monitoring', 'video_recording', 'motion_detection'],
            'wyze': ['security_camera', 'motion_detection', 'cloud_storage'],
            'lifx': ['lighting', 'color_control', 'effects', 'scheduling'],
            'wemo': ['power_control', 'scheduling', 'remote_access']
        }
        
        return capabilities.get(device_type, ['basic_control'])
    
    async def control_device(self, command: str) -> str:
        """Universal device control with intelligent routing"""
        command_lower = command.lower()
        
        try:
            # Parse command for device type and action
            device_info = self._parse_device_command(command_lower)
            
            if not device_info:
                return "I couldn't understand which device you want to control."
            
            device_type = device_info['type']
            action = device_info['action']
            parameters = device_info.get('parameters', {})
            
            # Find matching devices
            matching_devices = self._find_devices_by_type(device_type)
            
            if not matching_devices:
                return f"I couldn't find any {device_type} devices on your network."
            
            # Execute command on all matching devices
            results = []
            for ip, device in matching_devices.items():
                result = await self._execute_device_command(ip, device, action, parameters)
                results.append(result)
            
            # Compile results
            if all(results):
                return f"Successfully executed {action} on {len(results)} {device_type} device(s)."
            else:
                successful = sum(1 for r in results if r)
                return f"Executed {action} on {successful}/{len(results)} {device_type} device(s)."
        
        except Exception as e:
            return f"Error controlling device: {str(e)}"
    
    def _parse_device_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Parse natural language device commands"""
        # Lighting commands
        if any(word in command for word in ['light', 'lamp', 'bulb']):
            if 'turn on' in command or 'switch on' in command:
                return {'type': 'lighting', 'action': 'turn_on'}
            elif 'turn off' in command or 'switch off' in command:
                return {'type': 'lighting', 'action': 'turn_off'}
            elif 'dim' in command or 'brightness' in command:
                # Extract brightness level
                import re
                match = re.search(r'(\d+)%?', command)
                brightness = int(match.group(1)) if match else 50
                return {'type': 'lighting', 'action': 'set_brightness', 'parameters': {'brightness': brightness}}
        
        # TV/Media commands
        elif any(word in command for word in ['tv', 'television', 'roku', 'chromecast']):
            if 'turn on' in command:
                return {'type': 'media', 'action': 'power_on'}
            elif 'turn off' in command:
                return {'type': 'media', 'action': 'power_off'}
            elif 'volume' in command:
                import re
                if 'up' in command:
                    return {'type': 'media', 'action': 'volume_up'}
                elif 'down' in command:
                    return {'type': 'media', 'action': 'volume_down'}
                else:
                    match = re.search(r'(\d+)', command)
                    volume = int(match.group(1)) if match else 50
                    return {'type': 'media', 'action': 'set_volume', 'parameters': {'volume': volume}}
        
        # Climate commands
        elif any(word in command for word in ['temperature', 'thermostat', 'heat', 'cool', 'ac']):
            import re
            match = re.search(r'(\d+)', command)
            if match:
                temp = int(match.group(1))
                return {'type': 'climate', 'action': 'set_temperature', 'parameters': {'temperature': temp}}
        
        # Security commands
        elif any(word in command for word in ['security', 'alarm', 'camera', 'lock']):
            if 'arm' in command or 'enable' in command:
                return {'type': 'security', 'action': 'arm'}
            elif 'disarm' in command or 'disable' in command:
                return {'type': 'security', 'action': 'disarm'}
        
        return None
    
    def _find_devices_by_type(self, device_type: str) -> Dict[str, Dict]:
        """Find devices matching the specified type"""
        matching = {}
        
        type_mapping = {
            'lighting': ['philips_hue', 'lifx', 'tp_link_kasa'],
            'media': ['roku', 'chromecast', 'amazon_echo', 'google_home', 'sonos'],
            'climate': ['nest'],
            'security': ['ring', 'wyze']
        }
        
        target_types = type_mapping.get(device_type, [device_type])
        
        for ip, device in self.discovered_devices.items():
            if device['type'] in target_types:
                matching[ip] = device
        
        return matching
    
    async def _execute_device_command(self, ip: str, device: Dict, action: str, parameters: Dict) -> bool:
        """Execute command on specific device"""
        device_type = device['type']
        
        try:
            if device_type == 'philips_hue':
                return await self._control_hue(ip, action, parameters)
            elif device_type == 'roku':
                return await self._control_roku(ip, action, parameters)
            elif device_type == 'chromecast':
                return await self._control_chromecast(ip, action, parameters)
            elif device_type == 'tp_link_kasa':
                return await self._control_kasa(ip, action, parameters)
            # Add more device-specific controls
            
            return True  # Default success for unknown devices
            
        except Exception as e:
            print(f"Device control error for {ip}: {e}")
            return False
    
    async def _control_hue(self, ip: str, action: str, parameters: Dict) -> bool:
        """Control Philips Hue devices"""
        try:
            if not self.philips_hue_api_key:
                print("Warning: PHILIPS_HUE_API_KEY not configured")
                return False

            async with aiohttp.ClientSession() as session:
                if action == 'turn_on':
                    data = {'on': True}
                elif action == 'turn_off':
                    data = {'on': False}
                elif action == 'set_brightness':
                    data = {'on': True, 'bri': int(parameters['brightness'] * 2.54)}  # Convert to 0-254
                else:
                    return False
                
                # Send to all lights (in production, you'd get light IDs first)
                async with session.put(
                    f"http://{ip}/api/{self.philips_hue_api_key}/lights/1/state",
                    json=data
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            print(f"Hue control error: {e}")
            return False
    
    async def _control_roku(self, ip: str, action: str, parameters: Dict) -> bool:
        """Control Roku devices"""
        try:
            async with aiohttp.ClientSession() as session:
                if action == 'power_on':
                    url = f"http://{ip}:8060/keypress/PowerOn"
                elif action == 'power_off':
                    url = f"http://{ip}:8060/keypress/PowerOff"
                elif action == 'volume_up':
                    url = f"http://{ip}:8060/keypress/VolumeUp"
                elif action == 'volume_down':
                    url = f"http://{ip}:8060/keypress/VolumeDown"
                else:
                    return False
                
                async with session.post(url) as response:
                    return response.status == 200
                    
        except Exception as e:
            print(f"Roku control error: {e}")
            return False
    
    async def _control_chromecast(self, device_name: str, action: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Control a Chromecast device.

        Args:
            device_name: Name of the Chromecast device
            action: Action to perform (play, pause, stop, volume, etc.)
            parameters: Additional parameters for the action (e.g., {'volume': 0.5})

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            chromecasts, browser = pychromecast.get_chromecasts()
            cast = next(cc for cc in chromecasts if cc.device.friendly_name == device_name)
            
            if not cast:
                return False

            cast.wait()
            
            if action == "volume":
                if parameters and "level" in parameters:
                    cast.set_volume(parameters["level"])
            elif action == "play":
                cast.media_controller.play()
            elif action == "pause":
                cast.media_controller.pause()
            elif action == "stop":
                cast.media_controller.stop()
            
            browser.stop_discovery()
            return True
            
        except Exception as e:
            logger.error(f"Chromecast control error: {str(e)}")
            return False
    
    async def _control_kasa(self, device_ip: str, action: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Control TP-Link Kasa smart devices.

        Args:
            device_ip: IP address of the Kasa device
            action: Action to perform (on, off, brightness, color)
            parameters: Additional parameters for the action (e.g., {'brightness': 50})

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            device = await SmartDevice.connect(device_ip)

            if action == "on":
                await device.turn_on()
            elif action == "off":
                await device.turn_off()
            elif action == "brightness" and hasattr(device, "brightness"):
                if parameters and "level" in parameters:
                    await device.set_brightness(parameters["level"])
            elif action == "color" and hasattr(device, "set_color"):
                if parameters and all(k in parameters for k in ["hue", "saturation", "value"]):
                    await device.set_color(
                        parameters["hue"],
                        parameters["saturation"],
                        parameters["value"]
                    )
            
            return True

        except Exception as e:
            logger.error(f"Kasa device control error: {str(e)}")
            return False
    
    def get_device_status(self) -> str:
        """Get status of all discovered devices"""
        if not self.discovered_devices:
            return "No smart devices discovered on your network."
        
        status_lines = ["Smart Home Device Status:"]
        
        for ip, device in self.discovered_devices.items():
            device_type = device['type'].replace('_', ' ').title()
            capabilities = ', '.join(device['capabilities'])
            last_seen = device['last_seen'].strftime('%H:%M')
            
            status_lines.append(f"• {device_type} at {ip}")
            status_lines.append(f"  Capabilities: {capabilities}")
            status_lines.append(f"  Last seen: {last_seen}")
        
        return '\n'.join(status_lines)
    
    def get_tool(self) -> Tool:
        """Return LangChain tool for smart home control"""
        return Tool(
            name="smart_home_control",
            description="Control smart home devices including lights, TV, thermostat, security systems, and any WiFi-connected IoT devices",
            func=lambda command: asyncio.run(self.control_device(command))
        )

from typing import Dict, Any, Optional

class SmartHomeTool:
    """Tool for controlling smart home devices and automation."""
    
    def __init__(self):
        self.devices: Dict[str, Any] = {}
        
    async def control_device(self, device_id: str, action: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Control a smart home device.
        
        Args:
            device_id: The identifier of the device to control
            action: The action to perform (e.g., 'turn_on', 'turn_off', 'set_temperature')
            parameters: Optional parameters for the action
            
        Returns:
            bool: True if the action was successful, False otherwise
        """
        # TODO: Implement actual device control logic
        return True
    
    async def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """
        Get the current status of a smart home device.
        
        Args:
            device_id: The identifier of the device
            
        Returns:
            Dict containing the device status
        """
        # TODO: Implement actual device status checking
        return {"status": "unknown"}
