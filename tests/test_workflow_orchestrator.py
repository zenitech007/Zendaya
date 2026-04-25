"""
Tests for WorkflowOrchestrator
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from zendaya_backend.agent.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowTask,
    TaskStatus,
    TaskPriority
)
from zendaya_backend.agent.tools.tool_messaging import MessagingTool


@pytest.fixture
def mock_tools():
    """Create mock agent tools"""
    web_search_tool = Mock()
    web_search_tool.arun = AsyncMock(return_value="Search results")

    smart_home_tool = Mock()
    smart_home_tool.arun = AsyncMock(return_value="Device controlled successfully")

    calendar_tool = Mock()
    calendar_tool.arun = AsyncMock(return_value="Calendar checked")

    send_message_tool = Mock(spec=MessagingTool)
    send_message_tool.arun = AsyncMock(return_value="SMS sent to John successfully.")

    return {
        "web_search": web_search_tool,
        "smart_home_control": smart_home_tool,
        "calendar_check": calendar_tool,
        "send_message": send_message_tool
    }


@pytest.fixture
def orchestrator(mock_tools):
    """Create WorkflowOrchestrator instance"""
    return WorkflowOrchestrator(mock_tools)


class TestWorkflowTask:
    """Test WorkflowTask dataclass"""

    def test_workflow_task_creation(self):
        """Test creating a workflow task"""
        task = WorkflowTask(
            id="test_task_1",
            description="Test task",
            action="web_search",
            parameters={"query": "test"},
            dependencies=[],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING
        )

        assert task.id == "test_task_1"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL
        assert task.created_at is not None

    def test_workflow_task_defaults(self):
        """Test default values for workflow task"""
        task = WorkflowTask(
            id="test_task_2",
            description="Test task 2",
            action="smart_home_control",
            parameters={},
            dependencies=[],
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING
        )

        assert task.result is None
        assert task.error is None
        assert task.started_at is None
        assert task.completed_at is None


class TestWorkflowOrchestrator:
    """Test WorkflowOrchestrator"""

    @pytest.mark.asyncio
    async def test_process_simple_command(self, orchestrator):
        """Test processing a simple (non-complex) command"""
        result = await orchestrator.process_complex_command("turn on the lights")

        # A simple command should result in no tasks being parsed
        assert not result.get("tasks")

    @pytest.mark.asyncio
    async def test_process_complex_command_with_multiple_tasks(self, orchestrator, mock_tools):
        """Test processing a complex multi-step command"""
        command = "turn on the living room lights then check my calendar"

        with patch.object(orchestrator, '_parse_command_regex') as mock_parse:
            # Mock parsed tasks
            task1 = WorkflowTask(
                id="task_0_abc123",
                description="Turn on living room lights",
                action="smart_home_control",
                parameters={"command": "turn on the living room lights"},
                dependencies=[],
                priority=TaskPriority.NORMAL,
                status=TaskStatus.PENDING
            )

            task2 = WorkflowTask(
                id="task_1_def456",
                description="Check calendar",
                action="calendar_check",
                parameters={"query": "check my calendar"},
                dependencies=["task_0_abc123"],
                priority=TaskPriority.NORMAL,
                status=TaskStatus.PENDING
            )

            mock_parse.return_value = [task1, task2]

            result = await orchestrator.process_complex_command(command)

            assert "workflow_id" in result
            assert len(result.get("tasks", [])) == 2
            assert result["tasks"][0].description == "Turn on living room lights"

    @pytest.mark.asyncio
    async def test_parse_command_regex_fallback(self, orchestrator):
        """Test regex-based command parsing as fallback"""
        command = "turn on TV then send message to John"

        tasks = orchestrator._parse_command_regex(command)

        # Should parse into at least 2 tasks
        assert tasks is not None
        assert len(tasks) >= 2

        # First task should have no dependencies
        assert len(tasks[0].dependencies) == 0

        # Second task should depend on first
        assert len(tasks[1].dependencies) == 1
        assert tasks[1].dependencies[0] == tasks[0].id

    @pytest.mark.asyncio
    async def test_execute_single_task_smart_home(self, orchestrator, mock_tools):
        """Test executing a single smart home control task"""
        task = WorkflowTask(
            id="test_task",
            description="Control device",
            action="smart_home_control",
            parameters={"command": "turn on lights"},
            dependencies=[],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING
        )

        result = await orchestrator._execute_single_task(task)

        assert result == "Device controlled successfully"
        mock_tools["smart_home_control"].arun.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_task_web_search(self, orchestrator, mock_tools):
        """Test executing a web search task"""
        task = WorkflowTask(
            id="test_task",
            description="Search web",
            action="web_search",
            parameters={"query": "test query"},
            dependencies=[],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING
        )

        result = await orchestrator._execute_single_task(task)

        assert result == "Search results"
        mock_tools["web_search"].arun.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_task_send_message(self, orchestrator):
        """Test executing a send message task"""
        task = WorkflowTask(
            id="test_task",
            description="Send message",
            action="send_message",
            parameters={
                "recipient": "John",
                "message": "Hello",
                "platform": "sms"
            },
            dependencies=[],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING
        )

        result = await orchestrator._execute_single_task(task)

        assert "SMS sent to John" in result

    @pytest.mark.asyncio
    async def test_execute_workflow_with_dependencies(self, orchestrator, mock_tools):
        """Test executing workflow with task dependencies"""
        task1 = WorkflowTask(
            id="task_1",
            description="First task",
            action="web_search",
            parameters={"query": "test"},
            dependencies=[],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING
        )

        task2 = WorkflowTask(
            id="task_2",
            description="Second task",
            action="smart_home_control",
            parameters={"command": "test command"},
            dependencies=["task_1"],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PENDING
        )

        workflow = [task1, task2]
        results = await orchestrator._execute_workflow("test_workflow", workflow)

        assert len(results) == 2
        assert task1.status == TaskStatus.COMPLETED
        assert task2.status == TaskStatus.COMPLETED

        # Task 2 should complete after task 1
        assert task1.completed_at is not None
        assert task2.started_at is not None
        assert task1.completed_at <= task2.started_at

    def test_generate_workflow_report(self, orchestrator):
        """Test workflow report generation"""
        task1 = WorkflowTask(
            id="task_1",
            description="Task 1",
            action="web_search",
            parameters={},
            dependencies=[],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.COMPLETED
        )
        task1.result = "Task 1 completed successfully"
        task1.started_at = datetime.now()
        task1.completed_at = datetime.now()

        task2 = WorkflowTask(
            id="task_2",
            description="Task 2",
            action="smart_home_control",
            parameters={},
            dependencies=["task_1"],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.FAILED
        )
        task2.error = "Failed to execute"
        task2.started_at = datetime.now()
        task2.completed_at = datetime.now()

        workflow = [task1, task2]
        results = {
            "task_1": {"duration": 1.5},
            "task_2": {"duration": 0.5}
        }

        report = orchestrator._generate_workflow_report(workflow, results)

        assert "Task 1" in report
        assert "Task 2" in report
        assert "1/2 tasks successfully" in report
        assert "Failed to complete 1 task(s)" in report

    def test_get_workflow_status(self, orchestrator):
        """Test getting workflow status"""
        workflow_id = "test_workflow_123"

        task1 = WorkflowTask(
            id="task_1",
            description="Task 1",
            action="web_search",
            parameters={},
            dependencies=[],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.COMPLETED
        )

        task2 = WorkflowTask(
            id="task_2",
            description="Task 2",
            action="smart_home_control",
            parameters={},
            dependencies=["task_1"],
            priority=TaskPriority.NORMAL,
            status=TaskStatus.RUNNING
        )

        orchestrator.active_workflows[workflow_id] = [task1, task2]

        status = orchestrator.get_workflow_status(workflow_id)

        assert status is not None
        assert status["workflow_id"] == workflow_id
        assert status["total_tasks"] == 2
        assert status["completed"] == 1
        assert status["running"] == 1
        assert status["failed"] == 0

    def test_get_workflow_status_not_found(self, orchestrator):
        """Test getting status for non-existent workflow"""
        status = orchestrator.get_workflow_status("non_existent_workflow")
        assert status is None

    def test_split_command_by_patterns(self, orchestrator):
        """Test splitting commands by temporal patterns"""
        command = "do task A then do task B after doing task C"
        patterns = [r'\bthen\b', r'\bafter\b']

        segments = orchestrator._split_command_by_patterns(command, patterns)

        assert len(segments) == 3
        assert "task A" in segments[0]
        assert "task B" in segments[1]
        assert "task C" in segments[2]

    def test_extract_date(self, orchestrator):
        """Test extracting dates from text"""
        # Today
        date = orchestrator._extract_date("book restaurant for tonight")
        assert date == datetime.now().strftime('%Y-%m-%d')

        # Tomorrow
        from datetime import timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        date = orchestrator._extract_date("book restaurant for tomorrow")
        assert date == tomorrow

    def test_extract_time(self, orchestrator):
        """Test extracting time from text"""
        time = orchestrator._extract_time("book dinner at 7:30 PM")
        assert time == "19:30"

        # Default dinner time
        time = orchestrator._extract_time("book dinner reservation")
        assert time == "19:00"

    def test_detect_platform(self, orchestrator):
        """Test detecting messaging platform"""
        assert orchestrator._detect_platform("send WhatsApp message") == "whatsapp"
        assert orchestrator._detect_platform("send SMS to John") == "sms"
        assert orchestrator._detect_platform("send email") == "email"
        assert orchestrator._detect_platform("send message") == "sms"  # default

    @pytest.mark.asyncio
    async def test_process_complex_command(self, orchestrator):
        """Test processing a complex command"""
        command = "Search for weather and turn on lights"
        result = await orchestrator.process_complex_command(command)

        assert result is not None
        assert len(result['tasks']) == 2

    @pytest.fixture
    def send_message_tool(self):
        mock_tool = Mock(spec=MessagingTool)
        mock_tool.arun = AsyncMock(return_value="Message sent to test: hello")
        return mock_tool

    @pytest.mark.asyncio
    async def test_workflow_orchestrator_send_message(self, send_message_tool):
        # Now you can use send_message_tool in your test
        result = await send_message_tool.arun(recipient="test", message="hello")
        assert "test" in result
        assert "hello" in result