"""
Zendaya Agent - LangChain-powered action and tool execution with LLM-driven decisions
"""
import os
import asyncio
from typing import Dict, Any, List, Optional

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage
from dotenv import load_dotenv

from .tools.network_monitor import NetworkMonitorTool
from .tools.log_analyzer import LogAnalyzerTool
from .tools.threat_intelligence import ThreatIntelTool
from .tools.vulnerability_scanner import VulnerabilityScannerTool
from .tools.safe_browsing import SafeBrowsingTool
from zendaya_backend.ai_core.gemini_service import GeminiService # Needed for LogAnalyzerTool


from .tools.web_search import WebSearchTool
from .tools.calendar_manager import CalendarTool
from .tools.iot_controller import IoTTool

load_dotenv()

class ZendayaAgent:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.llm = None
        self.agent_executor = None
        self.tools = []
        self._initialize()

    def _initialize(self):
        """Initialize the LangChain agent with enhanced prompt engineering"""
        if not self.gemini_api_key:
            print("Warning: GEMINI_API_KEY not found - agent features disabled")
            return

        try:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=self.gemini_api_key,
                temperature=0.1
            )

            # Instantiate the Gemini service needed by the LogAnalyzerTool
            gemini_service_instance = GeminiService()

            # --- NEW: Instantiate all security tools ---
            self.tools = [
                WebSearchTool().get_tool(),
                CalendarTool().get_tool(),
                IoTTool().get_tool(),
                NetworkMonitorTool().get_tool(),
                LogAnalyzerTool(gemini_service_instance).get_tool(),
                ThreatIntelTool().get_tool(),
                VulnerabilityScannerTool().get_tool(),
                SafeBrowsingTool().get_tool(),
            ]

            # --- NEW: Enhanced system prompt with security tools ---
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=(
                    "You are Zendaya, a highly intelligent AI assistant with access to powerful tools for productivity and cybersecurity. "
                    "Your goal is to help users efficiently, accurately, and securely.\n\n"

                    "TOOL USAGE DECISION FRAMEWORK:\n"
                    "You have access to these tools:\n"
                    "1. web_search: For current information (weather, news, facts).\n"
                    "2. calendar_check: For schedule queries (meetings, appointments).\n"
                    "3. smart_home_control: For IoT device control (lights, TV, temperature).\n"
                    "4. discover_network_devices: Scans the local network for connected devices. Use when asked 'who is on my wifi?' or 'what devices are connected?'.\n"
                    "5. check_ip_reputation: Checks if an IP address is known for malicious activity.\n"
                    "6. scan_device_for_vulnerabilities: Runs a port scan on a local IP to find security weaknesses.\n"
                    "7. check_url_safety: Checks if a website link is safe to visit.\n"
                    "8. analyze_system_logs: Analyzes log files for security threats.\n\n"

                    "DECISION PROCESS:\n"
                    "1. Analyze: Does this query require external data, a physical action, or a security check?\n"
                    "2. If YES -> Select the most appropriate tool and use it.\n"
                    "3. If NO -> Provide a direct, helpful answer from your own knowledge.\n\n"

                    "SECURITY SCENARIOS:\n"
                    "- If asked 'Is this link safe?', use `check_url_safety`.\n"
                    "- If asked to 'scan my laptop for open ports', ask for the local IP address first, then use `scan_device_for_vulnerabilities`.\n"
                    "- If a log analysis returns a suspicious IP, use `check_ip_reputation` as a follow-up action.\n"
                )),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])

            agent = create_openai_functions_agent(self.llm, self.tools, prompt)
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,
                max_iterations=5, # Increased for multi-step security checks
                handle_parsing_errors=True
            )

            print("✅ Zendaya agent initialized with enhanced productivity and cybersecurity tools.")

        except Exception as e:
            print(f"❌ Failed to initialize agent: {e}")

    def is_ready(self) -> bool:
        """Check if agent is ready"""
        return self.agent_executor is not None

    async def process(self, message: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Process user message with LLM making all tool usage decisions
        The agent autonomously decides whether and which tools to use
        """
        if not self.is_ready():
            return {"actions": [], "result": "Agent system offline"}

        try:
            # Let LLM make ALL decisions - no pre-filtering
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.agent_executor.invoke({
                    "input": message,
                    "chat_history": []
                })
            )

            return {
                "actions": self._extract_actions(result),
                "result": result.get("output", "")
            }

        except Exception as e:
            print(f"Agent processing error: {e}")
            return {"actions": [], "result": f"Agent error: {str(e)}"}

    def _extract_actions(self, result: Dict[str, Any]) -> List[str]:
        """Extract executed actions from agent result"""
        actions = []

        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if hasattr(step, 'tool') and hasattr(step, 'tool_input'):
                    actions.append(f"Used {step.tool} with input: {step.tool_input}")

        return actions
