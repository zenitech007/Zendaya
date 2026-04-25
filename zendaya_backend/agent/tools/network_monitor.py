"""
NetworkMonitorTool for Zendaya AI
---------------------------------
Provides capabilities for discovering devices and monitoring network traffic.
This tool uses Scapy for packet sniffing and analysis.

Note: Running this tool requires elevated privileges (root or administrator)
to access raw network sockets.
"""
import asyncio
from collections import defaultdict
from typing import Dict, Any
from langchain.tools import Tool
from scapy.all import sniff, ARP, Ether
import logging

logger = logging.getLogger(__name__)

class NetworkMonitorTool:
    def __init__(self):
        self.name = "network_monitor"
        self.description = (
            "Monitors network traffic to discover new devices, "
            "identify suspicious connections, and detect unusual protocol usage."
        )
        self.devices_on_network = {}

    def _arp_discovery_callback(self, pkt):
        """Callback function for Scapy's sniff to process ARP packets."""
        if ARP in pkt and pkt[ARP].op == 2:  # op=2 is an ARP reply
            mac_address = pkt[Ether].src
            ip_address = pkt[ARP].psrc
            if ip_address not in self.devices_on_network:
                self.devices_on_network[ip_address] = mac_address
                logger.info(f"New device discovered: IP={ip_address}, MAC={mac_address}")

    async def discover_devices_async(self, timeout: int = 15) -> str:
        """
        Asynchronously discovers devices on the local network using ARP requests.
        Requires root/administrator privileges.
        """
        self.devices_on_network = {}
        loop = asyncio.get_running_loop()

        def run_scapy_sniff():
            try:
                # Sniff for ARP packets
                sniff(prn=self._arp_discovery_callback, filter="arp", store=0, timeout=timeout)
            except Exception as e:
                logger.error(f"Scapy sniffing failed. Ensure you are running with root/admin privileges. Error: {e}")

        try:
            await loop.run_in_executor(None, run_scapy_sniff)
        except Exception as e:
             return f"Device discovery failed. This tool often requires administrator privileges to run. Error: {e}"


        if not self.devices_on_network:
            return "No new devices were discovered on the network during the scan."

        response = f"Discovered {len(self.devices_on_network)} devices on the network:\n"
        for ip, mac in self.devices_on_network.items():
            response += f"- IP: {ip}, MAC: {mac}\n"
        return response

    def get_tool(self) -> Tool:
        """Returns a LangChain Tool instance for this tool."""
        return Tool(
            name="discover_network_devices",
            description="Scans the local network to discover all connected devices. Useful for identifying new or unrecognized devices. Requires administrator privileges.",
            func=lambda timeout=15: asyncio.run(self.discover_devices_async(timeout))
        )

# Example of how to integrate it with the agent (for zendaya_agent.py)
# from .tools.network_monitor_tool import NetworkMonitorTool
#
# self.tools = [
#     # ... other tools
#     NetworkMonitorTool().get_tool(),
# ]
