from pathlib import Path
from uuid import uuid4

from config import MAX_RETRIES
from llm.client import LLMClient
from llm.prompts import RETRY_PROMPT, SYSTEM_PROMPT
from sandbox.docker_runner import DockerRunner
from schemas.request import TaskRequest
from schemas.response import TaskResponse
from schemas.tool_calls import (
    ReadFileArgs,
    ToolCall,
    ToolName,
    WriteFileArgs,
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
        workspace = self.workspace_manager.create_workspace(f"task_{uuid4().hex}")

        execution = None

        for attempt in range(1, MAX_RETRIES + 1):
            tool_calls = self._generate_tool_calls(
                request=request,
                execution=execution,
                workspace=workspace,
                attempt=attempt,
            )

            for tool in tool_calls.tools:
                self._execute_tool(workspace, tool)

            execution = self.docker_runner.run(
                workspace=workspace,
                command=["python", "main.py"],
            )

            if execution.success:
                break

        return TaskResponse(
            success=execution.success,
            attempts=attempt,
            execution=execution,
        )

    def _generate_tool_calls(
        self,
        request: TaskRequest,
        execution,
        workspace: Path,
        attempt: int,
    ):
        if attempt == 1:
            return self.llm.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=request.prompt,
            )

        retry_prompt = RETRY_PROMPT.format(
            task=request.prompt,
            files=self._workspace_snapshot(workspace),
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            attempt=attempt,
        )

        return self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=retry_prompt,
        )

    def _workspace_snapshot(
        self,
        workspace: Path,
    ) -> str:
        """
        Returns the current workspace contents as formatted text.
        """

        sections = []

        for path in self.workspace_manager.list_files(workspace):
            content = self.workspace_manager.read_file(
                workspace,
                path,
            )

            sections.append(
                f"""FILE: {path}

                {content}
                """
            )

        return "\n".join(sections)

    def _execute_tool(
        self,
        workspace: Path,
        tool: ToolCall,
    ) -> None:
        """
        Execute a single tool call.
        Normalizes common argument aliases produced by the LLM.
        """

        arguments = dict(tool.arguments)

        match tool.tool:
            case ToolName.WRITE_FILE:
                # Common aliases
                if "file_path" in arguments:
                    arguments["path"] = arguments.pop("file_path")

                if "text" in arguments:
                    arguments["content"] = arguments.pop("text")

                if "code" in arguments:
                    arguments["content"] = arguments.pop("code")

                args = WriteFileArgs.model_validate(arguments)

                self.workspace_manager.write_file(
                    workspace=workspace,
                    relative_path=args.path,
                    content=args.content,
                )

            case ToolName.READ_FILE:
                # Common aliases
                if "file_path" in arguments:
                    arguments["path"] = arguments.pop("file_path")

                if "filename" in arguments:
                    arguments["path"] = arguments.pop("filename")

                args = ReadFileArgs.model_validate(arguments)

                self.workspace_manager.read_file(
                    workspace=workspace,
                    relative_path=args.path,
                )

            case ToolName.LIST_FILES:
                self.workspace_manager.list_files(workspace)

            case _:
                raise ValueError(f"Unsupported tool: {tool.tool}")
