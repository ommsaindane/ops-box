from pathlib import Path

from llm.client import LLMClient
from sandbox.docker_runner import DockerRunner
from schemas.request import TaskRequest
from schemas.response import TaskResponse
from schemas.tool_calls import (
    ToolCall,
    ToolCalls,
    ToolName,
    WriteFileArgs,
)
from workspace.manager import WorkspaceManager
from uuid import uuid4


class Orchestrator:
    def __init__(
        self,
        llm: LLMClient,
        workspace_manager: WorkspaceManager,
        docker_runner: DockerRunner,
    ):
        self.llm = llm
        self.workspace_manager = workspace_manager
        self.docker_runner = docker_runner

    def run(self, request: TaskRequest) -> TaskResponse:

        workspace = self.workspace_manager.create_workspace(f"task_{uuid4().hex}")

        response = self.llm.generate(request.prompt)

        tool_calls = ToolCalls.model_validate_json(response)

        for tool in tool_calls.tools:
            self._execute_tool(workspace, tool)

        execution = self.docker_runner.run(
            workspace=workspace,
            command=["python", "main.py"],
        )

        return TaskResponse(
            success=execution.success,
            attempts=1,
            execution=execution,
        )

    def _execute_tool(
        self,
        workspace: Path,
        tool: ToolCall,
    ) -> None:

        match tool.tool:
            case ToolName.WRITE_FILE:
                args = WriteFileArgs.model_validate(tool.arguments)

                self.workspace_manager.write_file(
                    workspace=workspace,
                    relative_path=args.path,
                    content=args.content,
                )

            case _:
                raise NotImplementedError(f"Unsupported tool: {tool.tool}")
