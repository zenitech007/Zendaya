"""
Zendaya Agent - LangChain-powered action and tool execution
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage
from dotenv import load_dotenv

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
        """Initialize the LangChain agent"""
        if not self.gemini_api_key:
            print("Warning: GEMINI_API_KEY not found - agent features disabled")
            return
        
        try:
            # Initialize Gemini LLM
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=self.gemini_api_key,
                temperature=0.1
            )
            
            # Initialize tools
            self.tools = [
                WebSearchTool().get_tool(),
                CalendarTool().get_tool(),
                IoTTool().get_tool()
            ]
            
            # Create agent prompt
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=(
                    "You are Zendaya's action execution system. You have access to various tools "
                    "to help users accomplish tasks. Use tools when the user's request requires "
                    "external data or actions. Be efficient and only use tools when necessary."
                )),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # Create agent
            agent = create_openai_functions_agent(self.llm, self.tools, prompt)
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,
                max_iterations=3
            )
            
            print("✅ Zendaya agent initialized with tools")
            
        except Exception as e:
            print(f"❌ Failed to initialize agent: {e}")
    
    def is_ready(self) -> bool:
        """Check if agent is ready"""
        return self.agent_executor is not None
    
    async def process(self, message: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Process user message and execute tools if needed"""
        if not self.is_ready():
            return {"actions": [], "result": "Agent system offline"}
        
        try:
            # Determine if tools are needed
            if not self._needs_tools(message):
                return {"actions": [], "result": "No tools needed"}
            
            # Execute agent
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
    
    def _needs_tools(self, message: str) -> bool:
        """Determine if the message requires tool usage"""
        tool_keywords = [
            "search", "look up", "find", "weather", "news", "latest",
            "calendar", "schedule", "appointment", "meeting",
            "control", "turn on", "turn off", "adjust", "set"
        ]
        
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in tool_keywords)
    
    def _extract_actions(self, result: Dict[str, Any]) -> List[str]:
        """Extract executed actions from agent result"""
        actions = []
        
        # This would be customized based on your specific tool implementations
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if hasattr(step, 'tool') and hasattr(step, 'tool_input'):
                    actions.append(f"Used {step.tool} with input: {step.tool_input}")
        
        return actions