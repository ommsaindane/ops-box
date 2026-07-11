from pydantic import BaseModel

from schemas.execution import ExecutionResult


class TaskResponse(BaseModel):
    success: bool
    attempts: int
    execution: ExecutionResult
