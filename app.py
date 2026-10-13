"""
app.py

Production-ready FastAPI application providing asynchronous task execution,
real-time SSE streaming of agent steps, and sandbox lifecycle management.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from llm.client import UniversalLLMClient
from orchestrator.orchestrator import (
    OpsOrchestrator,
    OrchestratorResult,
    StepTrace,
    TaskStatus,
)
from sandbox.docker_runner import HardenedDockerRunner
from workspace.manager import WorkspaceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ops-box")

# Shared Singletons
workspace_manager: Optional[WorkspaceManager] = None
docker_runner: Optional[HardenedDockerRunner] = None
llm_client: Optional[UniversalLLMClient] = None
orchestrator: Optional[OpsOrchestrator] = None

# In-memory store for active/completed task states & SSE event queues
task_store: Dict[str, Dict[str, Any]] = {}
task_event_queues: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Modern lifespan event handler replacing deprecated @app.on_event decorators."""
    global workspace_manager, docker_runner, llm_client, orchestrator

    workspace_manager = WorkspaceManager(base_dir="data/workspaces", default_ttl_seconds=3600)
    purged = workspace_manager.cleanup_expired_workspaces()
    logger.info("Workspace GC initialized. Cleaned %d expired workspace(s).", purged)

    try:
        docker_runner = HardenedDockerRunner(base_image="python:3.11-slim")
        llm_client = UniversalLLMClient()
        orchestrator = OpsOrchestrator(
            llm_client=llm_client,
            workspace_manager=workspace_manager,
            docker_runner=docker_runner,
            max_steps=10,
        )
        logger.info("Docker runner and orchestrator initialized successfully.")
    except Exception as exc:
        logger.warning("Docker/LLM startup initialization deferred: %s", exc)

    yield  # Application runs here

    logger.info("Shutting down Ops-Box engine.")


app = FastAPI(
    title="Ops-Box Execution Engine",
    description="Autonomous sandboxed code execution and operations agent.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateTaskRequest(BaseModel):
    instruction: str = Field(..., description="The objective or prompt for the operations agent.")
    max_steps: Optional[int] = Field(default=10, ge=1, le=25)


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    summary: Optional[str] = None
    total_duration_seconds: Optional[float] = None
    error: Optional[str] = None
    step_count: int = 0


async def background_task_runner(task_id: str, instruction: str) -> None:
    """Worker coroutine that runs the orchestrator loop and feeds the SSE queue."""
    if not orchestrator:
        logger.error("Orchestrator is not initialized.")
        return

    queue = task_event_queues.get(task_id)

    async def on_step_callback(step: StepTrace) -> None:
        if queue:
            payload = {
                "event": "step",
                "step_number": step.step_number,
                "thought": step.thought,
                "tool_name": step.tool_name,
                "tool_input": step.tool_input,
                "tool_output": step.tool_output,
                "exit_code": step.exit_code,
                "duration_seconds": round(step.duration_seconds, 2),
            }
            await queue.put(payload)

    task_store[task_id]["status"] = TaskStatus.RUNNING

    try:
        result: OrchestratorResult = await orchestrator.execute_task(
            task_id=task_id,
            task_instruction=instruction,
            on_step_callback=on_step_callback,
        )
        task_store[task_id]["status"] = result.status
        task_store[task_id]["summary"] = result.summary
        task_store[task_id]["total_duration_seconds"] = result.total_duration_seconds
        task_store[task_id]["steps"] = [s.__dict__ for s in result.steps]
        task_store[task_id]["error"] = result.error
    except Exception as exc:
        logger.exception("Task %s failed unexpectedly: %s", task_id, exc)
        task_store[task_id]["status"] = TaskStatus.FAILED
        task_store[task_id]["error"] = str(exc)
    finally:
        if queue:
            await queue.put({
                "event": "done",
                "status": task_store[task_id]["status"].value,
                "summary": task_store[task_id].get("summary", ""),
            })


@app.post("/api/v1/tasks", status_code=status.HTTP_202_ACCEPTED, response_model=TaskResponse)
async def submit_task(request: CreateTaskRequest, background_tasks: BackgroundTasks) -> TaskResponse:
    """Submits a new operations task for background execution."""
    task_id = uuid.uuid4().hex
    task_store[task_id] = {
        "task_id": task_id,
        "instruction": request.instruction,
        "status": TaskStatus.PENDING,
        "summary": None,
        "total_duration_seconds": None,
        "steps": [],
        "error": None,
    }
    task_event_queues[task_id] = asyncio.Queue()

    background_tasks.add_task(background_task_runner, task_id, request.instruction)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        step_count=0,
    )


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str) -> TaskResponse:
    """Fetches the current status and summary of a task."""
    task_data = task_store.get(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(
        task_id=task_id,
        status=task_data["status"],
        summary=task_data.get("summary"),
        total_duration_seconds=task_data.get("total_duration_seconds"),
        error=task_data.get("error"),
        step_count=len(task_data.get("steps", [])),
    )


@app.get("/api/v1/tasks/{task_id}/events")
async def stream_task_events(task_id: str) -> StreamingResponse:
    """Streams real-time execution steps and logs via Server-Sent Events (SSE)."""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")

    queue = task_event_queues.get(task_id)
    if not queue:
        raise HTTPException(status_code=400, detail="Event stream unavailable for this task")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                event_data = await queue.get()
                yield f"data: {json.dumps(event_data)}\n\n"
                if event_data.get("event") == "done":
                    break
        except asyncio.CancelledError:
            logger.info("SSE client disconnected from task %s", task_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health status endpoint."""
    return {"status": "ok", "engine": "ops-box"}