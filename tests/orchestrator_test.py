from llm.client import LLMClient
from orchestrator.orchestrator import Orchestrator
from sandbox.docker_runner import DockerRunner
from schemas.request import TaskRequest
from schemas.tool_calls import ToolCall, ToolCalls, ToolName
from workspace.manager import WorkspaceManager


class MockLLMClient(LLMClient):
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


def test_orchestrator_runs_python_program(tmp_path):
    workspace_manager = WorkspaceManager(root=tmp_path)

    docker_runner = DockerRunner()

    llm = MockLLMClient()

    orchestrator = Orchestrator(
        llm=llm,
        workspace_manager=workspace_manager,
        docker_runner=docker_runner,
    )

    request = TaskRequest(prompt="Write a hello world program.")

    response = orchestrator.run(request)

    assert response.success
    assert response.attempts == 1
    assert response.execution.exit_code == 0
    assert "Hello, Ops-Box!" in response.execution.stdout
