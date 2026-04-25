"""
Advanced Workflow Orchestrator - Production Ready
Merges robust lifecycle management with complete task execution logic for multi-step command processing.
"""
import asyncio
import json
import re
import os
import uuid
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta, time as datetime_time
from dataclasses import dataclass, field
from enum import Enum
import logging

from pydantic import SecretStr
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# --- CORRECTED IMPORT ---
from zendaya_backend.core.config import settings # Import the global settings object

from .tools.tool_messaging import MessagingTool
from .tools.web_search import WebSearchTool
from .tools.smart_home_controller import SmartHomeTool

load_dotenv()

logger = logging.getLogger(__name__)

# --- Data Models and Enums ---

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class WorkflowTask:
    id: str
    description: str
    action: str
    parameters: Dict[str, Any]
    dependencies: List[str]
    priority: TaskPriority
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

# agent/workflow_orchestrator.py (constructor)
class WorkflowOrchestrator:
    def __init__(self, tools=None, user_id: Optional[str] = None, context: Optional[dict] = None, **kwargs):
        """
        Backwards-compatible constructor.
        - `tools` (dict) is the preferred injection method.
        - Accept legacy keyword args like web_search_tool and smart_home_controller and map into tools.
        """
        # start with a shallow copy
        self.tools = dict(tools) if tools else {}

        # Accept and map legacy keyword args for tests/older code
        # map keys -> standardized tool names used in code
        legacy_map = {
            "web_search_tool": "web_search",
            "smart_home_controller": "smart_home",
            "voice_service": "voice_service",
            "rag_service": "rag_service",
            # add more mappings if your tests pass other named kwargs
        }
        for legacy_arg, standard_key in legacy_map.items():
            if legacy_arg in kwargs and kwargs[legacy_arg] is not None:
                self.tools[standard_key] = kwargs[legacy_arg]

        self.user_id = user_id
        self.context = context or {}
        # existing initialization...
        # Initialize LLM for intelligent command parsing
        self.llm = self._initialize_llm()

        self.active_workflows = {}
        self.task_queue = asyncio.Queue()
        self._processor_task = None

    def _initialize_llm(self) -> Optional[ChatGoogleGenerativeAI]:
        """Initializes the Gemini LLM if an API key is available."""
        # --- CORRECTED LOGIC ---
        try:
            # Use the imported global 'settings' object
            gemini_api_key = settings.gemini_api_key
            if not gemini_api_key:
                print("Warning: GEMINI_API_KEY not found in settings. Falling back to regex-based command parsing.")
                return None

            # The LangChain model expects the API key as a raw string.
            # If it's a SecretStr, we extract the value.
            api_key_value = gemini_api_key.get_secret_value() if isinstance(gemini_api_key, SecretStr) else gemini_api_key

            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=api_key_value,
                temperature=0.1,
                convert_system_message_to_human=True
            )
        except Exception as e:
            print(f"Error initializing LLM for workflow orchestrator: {e}")
            return None


    def _initialize_tools(self):
        """Initialize all available tools"""
        self.tools = {
            "web_search": WebSearchTool(),
            "smart_home": SmartHomeTool(),
            "send_message": MessagingTool(),  # Add messaging tool
            # ...other tools...
        }

    # ---------------- WinError 32 / File helpers ----------------

    def _safe_remove(self, path: str, retries: int = 5, delay: float = 0.1) -> bool:
        """
        Remove a file with retries to avoid PermissionError (WinError 32).
        Returns True if removed or not present; False if still present after retries.
        """
        if not path:
            return True
        for attempt in range(retries):
            try:
                if os.path.exists(path):
                    safe_delete(path)
                return True
            except PermissionError as e:
                # Windows file lock — wait and retry
                time.sleep(delay * (attempt + 1))
            except Exception:
                break
        return not os.path.exists(path)

    def _safe_write_bytes(self, path: str, data: bytes, retries: int = 5, delay: float = 0.1) -> bool:
        """
        Write bytes to a file with retry in case of PermissionError.
        """
        for attempt in range(retries):
            try:
                with open(path, "wb") as f:
                    f.write(data)
                return True
            except PermissionError:
                time.sleep(delay * (attempt + 1))
            except Exception:
                break
        return False

    # ---------------- Application Lifecycle Management ----------------

    async def startup(self):
        """Starts the background task processor safely after the event loop has started."""
        if self._processor_task is None or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_task_queue())
            print("INFO:     Workflow task processor started.")

    async def shutdown(self):
        """Stops the background task processor cleanly during application shutdown."""
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                print("INFO:     Workflow task processor stopped.")

    # ---------------- Public API ----------------

    async def process_complex_command(self, command: str) -> Dict[str, Any]:
        """Process a complex command into multiple tasks"""
        tasks = []

        # First try LLM parsing
        try:
            tasks = await self._parse_command_with_llm(command)
        except Exception as e:
            logger.warning(f"LLM parsing failed, falling back to regex parser. Error: {e}")
            tasks = self._parse_command_regex(command)  # Fix method name
        
        workflow_id = str(uuid.uuid4())
        return {
            "workflow_id": workflow_id,
            "tasks": tasks,
            "command": command,
            "created_at": datetime.now().isoformat()
        }

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the current status of an active or completed workflow."""
        tasks = self.active_workflows.get(workflow_id)
        if not tasks:
            return None

        return {
            "workflow_id": workflow_id,
            "total_tasks": len(tasks),
            "completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "running": len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            "failed": len([t for t in tasks if t.status == TaskStatus.FAILED]),
            "tasks": [{"id": t.id, "description": t.description, "status": t.status.value} for t in tasks]
        }

    # ---------------- Command Parsing (LLM with Regex Fallback) ----------------

    async def _parse_complex_command(self, command: str, user_context: Dict[str, Any] = {}) -> Optional[List[WorkflowTask]]:
        """
        Attempts to parse a command using the LLM; falls back to a regex-based method if the LLM fails or is unavailable.
        """
        if self.llm:
            try:
                llm_result = await self._parse_command_with_llm(command, user_context)
                if llm_result:
                    return llm_result
            except Exception as e:
                print(f"LLM parsing failed, falling back to regex parser. Error: {e}")

        return self._parse_command_regex(command, user_context)

    async def _parse_command_with_llm(self, command: str, user_context: Optional[Dict[str, Any]] = None) -> Optional[List[WorkflowTask]]:
        """Uses an LLM to parse a natural language command into a structured list of tasks."""
        if not self.llm:
            return None

        parsing_prompt = f"""
You are an expert task parser for an AI assistant. Your job is to convert a complex user command into a structured JSON array of tasks.

User Command: "{command}"

Available actions are: smart_home_control, send_message, web_search, restaurant_search, calendar_check.

Your output must be a valid JSON array where each object represents a single task. Each task must have:
- "description": A short, user-friendly description of the task.
- "action": The specific action to be performed from the available list.
- "parameters": A dictionary of all parameters needed for the action.
- "depends_on": A list of *indices* (0-based) of tasks that must be completed before this one can start. Use an empty list [] for no dependencies.

Analyze sequential cues like "then," "after that," "once that's done" to establish dependencies.

Return ONLY the JSON array.
"""
        response = await self.llm.ainvoke(parsing_prompt)
        response_text = str(response.content).strip()

        try:
            # Find and extract the JSON array from the LLM's response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start == -1 or json_end == 0:
                return None

            json_text = response_text[json_start:json_end]
            parsed_tasks = json.loads(json_text)

            if not isinstance(parsed_tasks, list) or len(parsed_tasks) < 2:
                return None  # Not a complex command if less than 2 tasks

            # Convert JSON objects to WorkflowTask dataclasses
            tasks, task_id_map = [], {}
            for i, task_data in enumerate(parsed_tasks):
                task_id = f"task_{i}_{uuid.uuid4().hex[:6]}"
                task_id_map[i] = task_id

                dependencies = [task_id_map[dep_idx] for dep_idx in task_data.get("depends_on", []) if dep_idx in task_id_map]

                tasks.append(WorkflowTask(
                    id=task_id,
                    description=task_data["description"],
                    action=task_data["action"],
                    parameters=task_data.get("parameters", {}),
                    dependencies=dependencies,
                    priority=TaskPriority.NORMAL,
                    status=TaskStatus.PENDING
                ))
            return tasks

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error decoding or parsing LLM response: {e}\nResponse was: {response_text}")
            return None

    def _parse_command_regex(self, command: str, user_context: Dict[str, Any] = {}) -> Optional[List[WorkflowTask]]:
        """Fallback regex-based parsing for commands with temporal connectors."""
        segments = self._split_command_by_patterns(command)

        # If splitting didn't produce multiple segments, still attempt a single-task parse
        if not segments or len(segments) < 2:
            return None

        tasks, last_task_id = [], None
        for i, segment in enumerate(filter(None, segments)):
            segment = segment.strip()
            dependencies = [last_task_id] if last_task_id else []
            task = self._parse_single_task_segment(segment, i, dependencies)
            if task:
                # attach parsed datetime/time info if present
                date = self._extract_date(segment)
                time_val = self._extract_time(segment)
                if date:
                    task.parameters.setdefault("scheduled_date", date)
                if time_val:
                    # if timedelta returned, convert to seconds offset
                    if isinstance(time_val, timedelta):
                        task.parameters.setdefault("scheduled_in_seconds", int(time_val.total_seconds()))
                    elif isinstance(time_val, datetime_time):
                        task.parameters.setdefault("scheduled_time", time_val.strftime("%H:%M:%S"))

                tasks.append(task)
                last_task_id = task.id

        return tasks if len(tasks) > 1 else None

    def _parse_single_task_segment(self, segment: str, index: int, dependencies: List[str]) -> Optional[WorkflowTask]:
        """Parses a single segment of a command into a task using regex."""
        segment_lower = segment.lower()
        task_id = f"task_{index}_{uuid.uuid4().hex[:6]}"

        # Simple keyword-based action detection
        if any(word in segment_lower for word in ['light', 'tv', 'thermostat', 'turn on', 'turn off']):
            action, params = "smart_home_control", {"command": segment}
        elif any(word in segment_lower for word in ['text', 'message', 'email', 'send message', 'send a message']):
            action, params = "send_message", {"recipient": "unknown", "message": segment}
        elif any(word in segment_lower for word in ['search', 'find', 'look up', 'google', 'lookup']):
            action, params = "web_search", {"query": segment}
        elif any(word in segment_lower for word in ['calendar', 'appointment', 'meeting', 'schedule']):
            action, params = "calendar_check", {"query": segment}
        else:
            return None  # Could not determine action

        # Detect likely platform and attach hint
        platform_hint = self._detect_platform(segment)
        if platform_hint != "unknown":
            params["platform"] = platform_hint

        return WorkflowTask(
            id=task_id, description=segment, action=action, parameters=params,
            dependencies=dependencies, priority=TaskPriority.NORMAL, status=TaskStatus.PENDING
        )

    # ---------------- New Helpers: splitting, date/time extraction, platform detection ----------------

    def _split_command_by_patterns(self, command: str, patterns: Optional[List[str]] = None) -> List[str]:
        """
        More robust splitting of a long command into task-like segments.
        Handles custom patterns if provided.
        """
        if not command or not isinstance(command, str):
            return []

        normalized = re.sub(r'[••\n\r\t;]+', '.', command)
        if patterns:
            regex = "|".join(patterns)
            parts = re.split(regex, normalized, flags=re.IGNORECASE)
        else:
            connectors = r'\bthen\b|\bafter that\b|\bafter\b|\bonce\b|\bwhen\b|\bnext\b|\band then\b|\band\b'
            parts = re.split(connectors, normalized, flags=re.IGNORECASE)
            if len(parts) <= 1:
                parts = re.split(r'[.!?]\s+|\n+', normalized)

        segments = [p.strip() for p in parts if p and p.strip()]
        return segments

    def _extract_date(self, text: str) -> str:
        """Extract date from text and return in YYYY-MM-DD format"""
        # Simple regex for date patterns
        patterns = [
            r'today',
            r'tomorrow',
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})'
        ]
        
        now = datetime.now()
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                if pattern == 'today':
                    return now.strftime('%Y-%m-%d')
                elif pattern == 'tomorrow':
                    return (now + timedelta(days=1)).strftime('%Y-%m-%d')
                else:
                    # Parse matched date parts
                    groups = match.groups()
                    if len(groups) == 3:
                        if len(groups[0]) == 4:  # YYYY-MM-DD
                            year, month, day = groups
                        else:  # DD/MM/YYYY
                            day, month, year = groups
                        year = int(year)
                        if year < 100:
                            year += 2000
                        return f"{year:04d}-{int(month):02d}-{int(day):02d}"
        
        return now.strftime('%Y-%m-%d')  # Default to today

    def _extract_time(self, text: str) -> str:
        """Extract time from text and return in HH:MM format (24-hour)"""
        # Default dinner time
        DEFAULT_DINNER_TIME = "19:00"
        
        # This regex captures hour, minute (optional), and period (optional)
        match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text.lower())
        
        if match:
            hour = int(match.group(1))
            minutes = int(match.group(2) or 0)
            period = match.group(3)

            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:  # Handle 12 AM (midnight)
                hour = 0

            return f"{hour:02d}:{minutes:02d}"

        # Handle default dinner time
        if "dinner" in text.lower():
            return DEFAULT_DINNER_TIME

        return "00:00"  # Default fallback

    def _detect_platform(self, text: str) -> str:
        """Detect messaging platform from text"""
        platforms = {
            'whatsapp': ['whatsapp', 'wa'],
            'sms': ['sms', 'text', 'message'],
            'email': ['email', 'mail']
        }
        
        text = text.lower()
        for platform, keywords in platforms.items():
            if any(keyword in text for keyword in keywords):
                return platform
                
        return "sms"  # Default to SMS

    # ---------------- Workflow & Task Execution ----------------

    async def _execute_workflow(self, workflow_id: str, tasks: List[WorkflowTask]) -> Dict[str, Any]:
        """
        Executes a list of tasks, respecting their dependencies. 
        Tasks with no dependencies are run concurrently.
        """
        results = {}
        completed_tasks = set()

        while len(completed_tasks) < len(tasks):
            ready_tasks = [
                task for task in tasks if task.status == TaskStatus.PENDING and
                all(dep in completed_tasks for dep in task.dependencies)
            ]

            if not ready_tasks:
                # Break if there are no ready tasks to prevent infinite loops (e.g., circular dependencies)
                remaining_tasks = [t for t in tasks if t.status == TaskStatus.PENDING]
                for task in remaining_tasks:
                    task.status = TaskStatus.FAILED
                    task.error = "Could not execute due to unmet or circular dependencies."
                break

            # Execute all currently ready tasks concurrently
            coroutines = [self._execute_single_task(task) for task in ready_tasks]
            task_results = await asyncio.gather(*coroutines, return_exceptions=True)

            # Process the results of the executed tasks
            for task, result in zip(ready_tasks, task_results):
                task.completed_at = datetime.now()
                if isinstance(result, Exception):
                    task.status, task.error = TaskStatus.FAILED, str(result)
                else:
                    task.status = TaskStatus.COMPLETED
                    task.result = str(result) if result is not None else None

                completed_tasks.add(task.id)
                results[task.id] = {
                    'description': task.description, 'status': task.status.value,
                    'result': task.result, 'error': task.error,
                    'duration': (task.completed_at - task.started_at).total_seconds() if task.started_at else 0
                }

        return results

    async def _execute_single_task(self, task: WorkflowTask) -> str:
        """Executes a single task by calling the appropriate agent tool."""
        task.status, task.started_at = TaskStatus.RUNNING, datetime.now()

        tool = self.tools.get(task.action)
        if not tool:
            raise ValueError(f"Action '{task.action}' is not supported. No matching tool found.")

        try:
            # Assumes all tools have an async `arun` method
            if "command" in task.parameters:
                return await tool.arun(task.parameters["command"])
            elif "query" in task.parameters:
                return await tool.arun(task.parameters["query"])
            else:
                # For tools that might take the whole parameter dict
                return await tool.arun(task.parameters)
        except Exception as e:
            raise Exception(f"Task '{task.description}' failed during execution: {e}")
        
    def _generate_workflow_report(self, workflow: List[WorkflowTask], results: Dict[str, Any]) -> str:
        total = len(workflow)
        successful = sum(1 for task in workflow if task.status == TaskStatus.COMPLETED)
        total_time = sum(results[task.id].get("duration", 0) for task in workflow if task.id in results)
        
        report = [
            f"{successful}/{total} tasks successfully completed in {total_time:.1f} seconds.\n"
        ]
        
        for task in workflow:
            status = "✅" if task.status == TaskStatus.COMPLETED else "❌"
            report.append(f"{status} {task.description}")
            if task.result:
                report.append(f"   - Result: {task.result}")
            if task.error:
                report.append(f"   - Error: {task.error}")
                
        if total - successful > 0:
            report.append(f"\nFailed to complete {total - successful} task(s).")
            
        return "\n".join(report)

    # ---------------- Background Processing & Reporting ----------------

    async def _process_task_queue(self):
        """Background task that processes the internal task queue."""
        while True:
            try:
                # Get next task from queue
                task = await self.task_queue.get()
                
                # Process the task
                try:
                    result = await self._execute_single_task(task)
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                finally:
                    task.completed_at = datetime.now()
                    self.task_queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing task queue: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on errors

# ---------------- Safe File Handling Utilities ----------------

import time

def safe_delete(path: str, retries: int = 5, delay: float = 0.2) -> bool:
    """
    Safely deletes a file, retrying if locked by another process (e.g., WinError 32 on Windows).
    Returns True if deleted successfully, False otherwise.
    """
    import os

    for attempt in range(retries):
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except PermissionError:
            time.sleep(delay * (attempt + 1))
        except Exception:
            break
    return False


