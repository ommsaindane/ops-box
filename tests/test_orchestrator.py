"""
tests/test_orchestrator.py

Unit tests for OpsOrchestrator: iterative execution, circuit breakers, and self-healing.
"""

from typing import Any, Dict, List
from unittest.mock import AsyncMock
import pytest
from pathlib import Path

from orchestrator.orchestrator import (
    OpsOrchestrator,
    TaskStatus,
    LLMStepResponse,
    ToolCallRequest,
)
from sandbox.docker_runner import ExecutionResult
from workspace.manager import WorkspaceManager


class MockLLMClient:
    """Mock LLM client configured with a sequence of canned step responses."""

    def __init__(self, responses: List[LLMStepResponse]):
        self.responses = list(responses)
        self.invocation_count = 0

    async def generate_step(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> LLMStepResponse:
        if self.invocation_count < len(self.responses):
            resp = self.responses[self.invocation_count]
            self.invocation_count += 1
            return resp
        # Default terminal response if responses run out
        return LLMStepResponse(
            thought="Task is done",
            tool_calls=[ToolCallRequest(name="finish_task", arguments={"summary": "Default done."})],
        )


@pytest.fixture
def mock_docker_runner():
    runner = AsyncMock()
    runner.run_command.return_value = ExecutionResult(
        exit_code=0,
        stdout="Output: All tests passed",
        stderr="",
        timed_out=False,
    )
    return runner


@pytest.mark.asyncio
async def test_orchestrator_successful_flow(tmp_path: Path, mock_docker_runner):
    ws_mgr = WorkspaceManager(base_dir=tmp_path / "workspaces")
    
    mock_responses = [
        # Step 1: Write file
        LLMStepResponse(
            thought="I will write solution.py",
            tool_calls=[
                ToolCallRequest(
                    name="write_file",
                    arguments={"path": "solution.py", "content": "print('42')"},
                )
            ],
        ),
        # Step 2: Run command
        LLMStepResponse(
            thought="Running the script to test",
            tool_calls=[
                ToolCallRequest(
                    name="run_command",
                    arguments={"command": "python solution.py"},
                )
            ],
        ),
        # Step 3: Finish task
        LLMStepResponse(
            thought="Execution verified",
            tool_calls=[
                ToolCallRequest(
                    name="finish_task",
                    arguments={"summary": "Successfully calculated result."},
                )
            ],
        ),
    ]

    llm = MockLLMClient(mock_responses)
    orchestrator = OpsOrchestrator(
        llm_client=llm,
        workspace_manager=ws_mgr,
        docker_runner=mock_docker_runner,
        max_steps=5,
    )

    result = await orchestrator.execute_task(
        task_id="test_run",
        task_instruction="Calculate 42",
    )

    assert result.status == TaskStatus.COMPLETED
    assert result.summary == "Successfully calculated result."
    assert len(result.steps) == 3
    assert result.steps[0].tool_name == "write_file"
    assert result.steps[1].tool_name == "run_command"
    assert result.steps[2].tool_name == "finish_task"


@pytest.mark.asyncio
async def test_orchestrator_max_steps_circuit_breaker(tmp_path: Path, mock_docker_runner):
    ws_mgr = WorkspaceManager(base_dir=tmp_path / "workspaces")

    # LLM keeps repeating the same command without ever finishing
    infinite_loop_response = [
        LLMStepResponse(
            thought="Repeating step...",
            tool_calls=[
                ToolCallRequest(
                    name="run_command",
                    arguments={"command": "echo 'still trying'"},
                )
            ],
        )
        for _ in range(5)
    ]

    llm = MockLLMClient(infinite_loop_response)
    orchestrator = OpsOrchestrator(
        llm_client=llm,
        workspace_manager=ws_mgr,
        docker_runner=mock_docker_runner,
        max_steps=3,  # Strict circuit breaker limit
    )

    result = await orchestrator.execute_task(
        task_id="breaker_task",
        task_instruction="Loop forever",
    )

    assert result.status == TaskStatus.STEP_LIMIT_EXCEEDED
    assert len(result.steps) == 3
    assert "maximum iteration limit" in result.summary