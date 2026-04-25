"""
LogAnalyzerTool for Zendaya AI
------------------------------
This tool is designed to receive log data, which would be streamed from
client-side agents, and use an LLM to analyze it for security patterns,
correlate events, and identify critical errors.
"""
from typing import Dict, Any, List
from langchain.tools import Tool
from zendaya_backend.ai_core.gemini_service import GeminiService
import logging

logger = logging.getLogger(__name__)

class LogAnalyzerTool:
    def __init__(self, gemini_service: GeminiService):
        self.name = "log_analyzer"
        self.description = "Analyzes system and application logs to identify security threats, correlate events, and summarize critical errors."
        self.gemini_service = gemini_service

    async def analyze_logs(self, logs: List[str]) -> str:
        """
        Uses the Gemini model to analyze a batch of log entries.
        """
        if not self.gemini_service or not self.gemini_service.is_ready():
            return "Log analysis is currently unavailable as the AI core is offline."

        if not logs:
            return "No logs provided to analyze."

        log_block = "\n".join(logs)
        prompt = f"""
        You are a senior cybersecurity analyst. Your task is to analyze the following log entries, identify any potential security incidents, and provide a concise summary.

        Look for patterns such as:
        - Repeated failed login attempts (brute-force attacks).
        - Successful logins from unusual IP addresses or at odd hours.
        - Critical application errors or crashes that could be security-related.
        - Evidence of malware or unauthorized software installation.

        Log entries:
        ---
        {log_block}
        ---

        Provide your analysis in a brief, easy-to-understand summary. If no threats are found, state that the logs appear normal.
        """

        try:
            response = await self.gemini_service.generate_response(prompt)
            return response
        except Exception as e:
            logger.error(f"Error during log analysis with Gemini: {e}")
            return "An error occurred while analyzing the logs."

    def get_tool(self) -> Tool:
        """Returns a LangChain Tool instance for this tool."""
        return Tool(
            name="analyze_system_logs",
            description="Analyzes a list of log entries for security threats and critical errors. The input should be a list of log strings.",
            func=lambda logs: asyncio.run(self.analyze_logs(logs))
        )
