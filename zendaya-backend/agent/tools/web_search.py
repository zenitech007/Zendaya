"""
Web Search Tool - Tavily API integration
"""
import os
import httpx
from typing import Dict, Any
from langchain.tools import Tool
from dotenv import load_dotenv

load_dotenv()

class WebSearchTool:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
    
    def search(self, query: str) -> str:
        """Search the web using Tavily API"""
        if not self.api_key:
            return "Web search unavailable - missing TAVILY_API_KEY"
        
        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 5
                    }
                )
                
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    return "No search results found."
                
                formatted_results = []
                for result in results:
                    title = result.get("title", "Untitled")
                    content = result.get("content", "")[:200]
                    url = result.get("url", "")
                    formatted_results.append(f"**{title}**\n{content}\nSource: {url}")
                
                return "\n\n".join(formatted_results)
                
        except Exception as e:
            return f"Search error: {str(e)}"
    
    def get_tool(self) -> Tool:
        """Return LangChain tool"""
        return Tool(
            name="web_search",
            description="Search the web for current information, news, facts, or answers to questions",
            func=self.search
        )