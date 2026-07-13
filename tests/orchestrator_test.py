from llm.client import LLMClient
from orchestrator.orchestrator import Orchestrator
from sandbox.docker_runner import DockerRunner
from schemas.request import TaskRequest
from schemas.tool_calls import (
    ToolCall,
    ToolCalls,
    ToolName,
)
from workspace.manager import WorkspaceManager


class SuccessLLM(LLMClient):
    def generate(self, system_prompt: str, user_prompt: str) -> ToolCalls:
        return ToolCalls(
            tools=[
                ToolCall(
                    tool=ToolName.WRITE_FILE,
                    arguments={
                        "path": "main.py",
                        "content": 'print("Hello, Ops-Box!")',
                    },
                )
            ]
        )


class RetryLLM(LLMClient):
    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt: str, user_prompt: str) -> ToolCalls:
        self.calls += 1

        if self.calls == 1:
            return ToolCalls(
                tools=[
                    ToolCall(
                        tool=ToolName.WRITE_FILE,
                        arguments={
                            "path": "main.py",
                            "content": 'raise RuntimeError("boom")',
                        },
                    )
                ]
            )

        return ToolCalls(
            tools=[
                ToolCall(
                    tool=ToolName.WRITE_FILE,
                    arguments={
                        "path": "main.py",
                        "content": 'print("fixed")',
                    },
                )
            ]
        )


def test_orchestrator_success(tmp_path):
    workspace_manager = WorkspaceManager(root=tmp_path)

    orchestrator = Orchestrator(
        llm=SuccessLLM(),
        workspace_manager=workspace_manager,
        docker_runner=DockerRunner(),
    )

    response = orchestrator.run(TaskRequest(prompt="Write a hello world program."))

    assert response.success
    assert response.attempts == 1
    assert response.execution.exit_code == 0
    assert "Hello, Ops-Box!" in response.execution.stdout


def test_orchestrator_retry(tmp_path):
    workspace_manager = WorkspaceManager(root=tmp_path)

    llm = RetryLLM()

    orchestrator = Orchestrator(
        llm=llm,
        workspace_manager=workspace_manager,
        docker_runner=DockerRunner(),
    )

    response = orchestrator.run(TaskRequest(prompt="Write a hello world program."))

    assert response.success
    assert response.attempts == 2
    assert response.execution.exit_code == 0
    assert "fixed" in response.execution.stdout

    assert llm.calls == 2
