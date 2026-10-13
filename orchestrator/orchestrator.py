"""
orchestrator/orchestrator.py

Autonomous operations loop coordinating LLM reasoning, sandboxed execution,
and ephemeral workspace management with deterministic circuit breakers.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Protocol

from sandbox.docker_runner import ExecutionResult, HardenedDockerRunner
from workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STEP_LIMIT_EXCEEDED = "step_limit_exceeded"


@dataclass(frozen=True)
class ToolCallRequest:
    """Represents a structured tool execution request from the LLM."""
    name: str
    arguments: Dict[str, Any]
    call_id: str = ""


@dataclass(frozen=True)
class LLMStepResponse:
    """Standardized output from the LLM client per iteration."""
    thought: Optional[str]
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    raw_content: Optional[str] = None


class LLMClientProtocol(Protocol):
    """Protocol decoupling orchestrator from specific vendor LLM clients."""
    async def generate_step(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> LLMStepResponse:
        ...


@dataclass
class StepTrace:
    """Detailed audit record of an individual execution step."""
    step_number: int
    thought: Optional[str]
    tool_name: Optional[str]
    tool_input: Dict[str, Any]
    tool_output: str
    exit_code: Optional[int]
    duration_seconds: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class OrchestratorResult:
    """Final outcome of an autonomous task execution run."""
    task_id: str
    status: TaskStatus
    summary: str
    steps: List[StepTrace] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "summary": self.summary,
            "total_duration_seconds": round(self.total_duration_seconds, 3),
            "error": self.error,
            "steps": [asdict(step) for step in self.steps],
        }


# Standard tools schema exposed to the LLM
SYSTEM_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes or overwrites text content to a file inside the task workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path of the target file."},
                    "content": {"type": "string", "description": "Full text content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads text content of a file from the task workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path of the file to read."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Lists all existing files and directory structure in the task workspace.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Executes a shell command inside the isolated Linux sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute inside /workspace.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Optional timeout in seconds (default 15).",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_task",
            "description": "Terminates the execution loop and provides the final solution summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Detailed explanation of the final result, changes made, and verification output.",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]


class OpsOrchestrator:
    """
    Executes an autonomous problem-solving loop using Docker sandboxing and filesystem isolation.
    """

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        workspace_manager: WorkspaceManager,
        docker_runner: HardenedDockerRunner,
        max_steps: int = 10,
        max_output_chars_to_llm: int = 4000,
    ) -> None:
        self.llm_client = llm_client
        self.workspace_manager = workspace_manager
        self.docker_runner = docker_runner
        self.max_steps = max_steps
        self.max_output_chars_to_llm = max_output_chars_to_llm

    async def execute_task(
        self,
        task_id: str,
        task_instruction: str,
        on_step_callback: Optional[Callable[[StepTrace], Awaitable[None]]] = None,
    ) -> OrchestratorResult:
        """
        Runs the full autonomous loop for a given task instruction.
        """
        start_time = time.time()
        workspace_path = self.workspace_manager.create_workspace(task_id)

        system_prompt = (
            "You are Ops-Box, an autonomous operations and software engineering agent.\n"
            "You have access to an isolated Linux sandbox with Python 3.11 pre-installed.\n"
            "Your workspace directory is mounted at `/workspace`.\n"
            "Guidelines:\n"
            "1. Plan your solution incrementally.\n"
            "2. Write necessary files, run commands to execute or test them, and inspect outputs.\n"
            "3. If an error or unexpected exit code occurs, inspect the output and debug your code.\n"
            "4. When the task is verified and complete, call `finish_task` with a clear summary.\n"
            "Always use the provided tools to interact with the environment."
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_instruction},
        ]

        steps: List[StepTrace] = []

        for step_idx in range(1, self.max_steps + 1):
            step_start = time.time()

            try:
                llm_response = await self.llm_client.generate_step(
                    messages=messages,
                    tools=SYSTEM_TOOLS_SCHEMA,
                )
            except Exception as exc:
                logger.exception("LLM generation failed on step %d: %s", step_idx, exc)
                return OrchestratorResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    summary="Execution aborted due to an LLM provider error.",
                    steps=steps,
                    total_duration_seconds=time.time() - start_time,
                    error=str(exc),
                )

            # Check if LLM emitted no tool calls
            if not llm_response.tool_calls:
                logger.warning("Step %d: LLM returned no tool call. Ending cycle.", step_idx)
                assistant_msg = {"role": "assistant", "content": llm_response.thought or ""}
                messages.append(assistant_msg)
                
                # Prompt the LLM to take action or finish
                messages.append({
                    "role": "user",
                    "content": "Please invoke a tool (e.g., run_command, write_file, or finish_task) to proceed.",
                })
                continue

            # Process the first tool call for deterministic serial execution
            tool_call = llm_response.tool_calls[0]

            # Append assistant's turn with tool call to context
            messages.append({
                "role": "assistant",
                "content": llm_response.thought or "",
                "tool_calls": [
                    {
                        "id": tool_call.call_id or f"call_{step_idx}",
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments),
                        },
                    }
                ],
            })

            # Check for terminal finish_task
            if tool_call.name == "finish_task":
                summary = str(tool_call.arguments.get("summary", "Task completed."))
                step_record = StepTrace(
                    step_number=step_idx,
                    thought=llm_response.thought,
                    tool_name="finish_task",
                    tool_input=tool_call.arguments,
                    tool_output=summary,
                    exit_code=0,
                    duration_seconds=time.time() - step_start,
                )
                steps.append(step_record)
                if on_step_callback:
                    await on_step_callback(step_record)

                return OrchestratorResult(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    summary=summary,
                    steps=steps,
                    total_duration_seconds=time.time() - start_time,
                )

            # Dispatch intermediate tool execution
            tool_output, exit_code = await self._dispatch_tool(
                task_id=task_id,
                workspace_path=workspace_path,
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
            )

            # Record step trace
            step_record = StepTrace(
                step_number=step_idx,
                thought=llm_response.thought,
                tool_name=tool_call.name,
                tool_input=tool_call.arguments,
                tool_output=tool_output,
                exit_code=exit_code,
                duration_seconds=time.time() - step_start,
            )
            steps.append(step_record)
            if on_step_callback:
                await on_step_callback(step_record)

            # Truncate output before appending to context to avoid prompt overflow
            safe_tool_output = tool_output
            if len(safe_tool_output) > self.max_output_chars_to_llm:
                safe_tool_output = (
                    safe_tool_output[: self.max_output_chars_to_llm]
                    + f"\n... [Output truncated to {self.max_output_chars_to_llm} characters]"
                )

            # Feed tool observation back to conversation history
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.call_id or f"call_{step_idx}",
                "name": tool_call.name,
                "content": safe_tool_output,
            })

        # Exceeded step limit
        return OrchestratorResult(
            task_id=task_id,
            status=TaskStatus.STEP_LIMIT_EXCEEDED,
            summary=f"Task reached maximum iteration limit of {self.max_steps} steps without calling finish_task.",
            steps=steps,
            total_duration_seconds=time.time() - start_time,
            error="Max steps exceeded.",
        )

    async def _dispatch_tool(
        self,
        task_id: str,
        workspace_path: Path,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> tuple[str, Optional[int]]:
        """
        Executes a tool within the safe isolation boundary and returns (output, exit_code).
        Catches all filesystem and container exceptions so the agent can self-correct.
        """
        try:
            if tool_name == "write_file":
                path = arguments.get("path")
                content = arguments.get("content", "")
                if not path:
                    return "Error: Missing required argument 'path'.", 1
                self.workspace_manager.write_file(task_id, path, content)
                return f"Successfully wrote {len(content)} characters to {path}", 0

            elif tool_name == "read_file":
                path = arguments.get("path")
                if not path:
                    return "Error: Missing required argument 'path'.", 1
                file_content = self.workspace_manager.read_file(task_id, path)
                return file_content, 0

            elif tool_name == "list_files":
                file_infos = self.workspace_manager.list_files(task_id)
                if not file_infos:
                    return "Workspace is currently empty.", 0
                lines = [f"- {info.filename} ({info.size_bytes} bytes)" for info in file_infos]
                return "\n".join(lines), 0

            elif tool_name == "run_command":
                command = arguments.get("command")
                if not command:
                    return "Error: Missing required argument 'command'.", 1
                timeout = arguments.get("timeout")

                # Parse command safely into a shell command invocation
                exec_cmd = ["/bin/sh", "-c", command]
                result: ExecutionResult = await self.docker_runner.run_command(
                    workspace_host_path=workspace_path,
                    command=exec_cmd,
                    timeout=timeout,
                )

                output_parts: List[str] = []
                if result.stdout:
                    output_parts.append(f"[STDOUT]\n{result.stdout}")
                if result.stderr:
                    output_parts.append(f"[STDERR]\n{result.stderr}")
                if result.timed_out:
                    output_parts.append(f"[TIMEOUT] Command timed out (exit code: {result.exit_code}).")
                if result.error_message and not result.timed_out:
                    output_parts.append(f"[ERROR] {result.error_message}")

                combined_output = "\n".join(output_parts) or "(Command executed with no output)"
                return combined_output, result.exit_code

            else:
                return f"Error: Unknown tool name '{tool_name}'. Available: write_file, read_file, list_files, run_command, finish_task", 1

        except PermissionError as perm_err:
            return f"Security Error: {str(perm_err)}", 1
        except FileNotFoundError as fnf_err:
            return f"Filesystem Error: {str(fnf_err)}", 1
        except Exception as exc:
            logger.exception("Unexpected error executing tool '%s': %s", tool_name, exc)
            return f"Runtime Tool Execution Error: {str(exc)}", 1