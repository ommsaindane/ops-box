from pathlib import Path
from uuid import uuid4

from llm.client import LLMClient
from llm.prompts import SYSTEM_PROMPT
from sandbox.docker_runner import DockerRunner
from schemas.request import TaskRequest
from schemas.response import TaskResponse
from schemas.tool_calls import (
    ToolCall,
    ToolName,
    WriteFileArgs,
    ReadFileArgs,
)
from workspace.manager import WorkspaceManager


class Orchestrator:
    """
    Coordinates the autonomous development workflow.
    """

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
        """
        Executes a single autonomous coding attempt.
        """

        workspace = self.workspace_manager.create_workspace(f"task_{uuid4().hex}")

        tool_calls = self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=request.prompt,
        )

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

            case ToolName.READ_FILE:
                args = ReadFileArgs.model_validate(tool.arguments)

                self.workspace_manager.read_file(
                    workspace=workspace,
                    relative_path=args.path,
                )

            case ToolName.LIST_FILES:
                self.workspace_manager.list_files(workspace)

            case _:
                raise ValueError(f"Unsupported tool: {tool.tool}")
