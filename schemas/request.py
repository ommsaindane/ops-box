from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    prompt: str = Field(..., description="User's development request")
