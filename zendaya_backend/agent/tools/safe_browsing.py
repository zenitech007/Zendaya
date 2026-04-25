"""
SafeBrowsingTool for Zendaya AI
-------------------------------
Integrates with the Google Safe Browsing API to check if URLs are malicious.
"""
import os
import httpx
from typing import Dict, Any, List
from langchain.tools import Tool
import logging

logger = logging.getLogger(__name__)

class SafeBrowsingTool:
    def __init__(self):
        self.name = "safe_browsing"
        self.description = "Uses the Google Safe Browsing API to check if a URL is potentially malicious, a phishing site, or contains malware."
        self.api_key = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")
        self.base_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={self.api_key}"

    async def check_url(self, url_to_check: str) -> str:
        """
        Checks a single URL against the Google Safe Browsing API.
        """
        if not self.api_key:
            return "Safe Browsing service is not configured. Please set the GOOGLE_SAFE_BROWSING_API_KEY environment variable."

        payload = {
            "client": {
                "clientId": "zendaya-ai",
                "clientVersion": "1.0.0"
            },
            "threatInfo": {
                "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [
                    {"url": url_to_check}
                ]
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload)

            if response.status_code == 200:
                data = response.json()
                if "matches" in data:
                    threat_type = data["matches"][0]["threatType"]
                    return f"Warning: The URL is flagged as a potential threat. Threat type: {threat_type}. I strongly advise against visiting it."
                else:
                    return "The URL appears to be safe according to Google's analysis."
            else:
                return f"Error checking URL. API returned status code: {response.status_code}. Details: {response.text}"
        except Exception as e:
            logger.error(f"Error calling Google Safe Browsing API: {e}")
            return "An error occurred while checking the URL's safety."

    def get_tool(self) -> Tool:
        """Returns a LangChain Tool instance for this tool."""
        return Tool(
            name="check_url_safety",
            description="Checks a given URL against the Google Safe Browsing list to determine if it is malicious or unsafe.",
            func=lambda url: asyncio.run(self.check_url(url))
        )
