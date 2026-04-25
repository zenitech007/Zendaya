"""
ThreatIntelTool for Zendaya AI
------------------------------
Integrates with threat intelligence APIs to check the reputation of IP addresses,
domains, and file hashes. This implementation uses AbuseIPDB as an example.
"""
import os
import httpx
from typing import Dict, Any
from langchain.tools import Tool
import logging

logger = logging.getLogger(__name__)

class ThreatIntelTool:
    def __init__(self):
        self.name = "threat_intelligence"
        self.description = "Checks IP addresses, domains, or file hashes against public threat intelligence feeds to identify known malicious entities."
        self.abuseipdb_api_key = os.getenv("ABUSEIPDB_API_KEY")
        self.base_url = "https://api.abuseipdb.com/api/v2/check"

    async def check_ip_reputation(self, ip_address: str) -> str:
        """
        Checks the reputation of an IP address using the AbuseIPDB API.
        """
        if not self.abuseipdb_api_key:
            return "Threat intelligence service is not configured. Please set the ABUSEIPDB_API_KEY environment variable."

        headers = {
            'Accept': 'application/json',
            'Key': self.abuseipdb_api_key,
        }
        params = {
            'ipAddress': ip_address,
            'maxAgeInDays': '90'
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json().get('data', {})
                if not data:
                    return f"No data found for IP address: {ip_address}"

                if data['abuseConfidenceScore'] > 50:
                    report_count = data['totalReports']
                    country = data['countryName']
                    return (f"Warning: IP address {ip_address} (from {country}) has a high abuse confidence score of {data['abuseConfidenceScore']}% "
                            f"based on {report_count} reports. It is likely malicious.")
                else:
                    return f"IP address {ip_address} has a low abuse confidence score of {data['abuseConfidenceScore']}%. It appears to be safe."
            else:
                return f"Error checking IP reputation. API returned status code: {response.status_code}"
        except Exception as e:
            logger.error(f"Error calling AbuseIPDB API: {e}")
            return "An error occurred while checking the IP reputation."

    def get_tool(self) -> Tool:
        """Returns a LangChain Tool instance for this tool."""
        return Tool(
            name="check_ip_reputation",
            description="Checks the reputation of a given IP address against a threat intelligence database to see if it is malicious.",
            func=lambda ip: asyncio.run(self.check_ip_reputation(ip))
        )
